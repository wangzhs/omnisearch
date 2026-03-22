from datetime import datetime, timedelta, timezone

from app.collectors.akshare import AKShareCollector
from app.collectors.cninfo import CNInfoCollector
from app.collectors.exchange_search import ExchangeSearchCollector
from app.collectors.tushare import TushareCollector
from app.core.config import settings
from app.db.base import StockRepository
from app.db.sqlite import get_repository
from app.models.stock import CompanyProfile, Event, FinancialSummary, PriceDaily
from app.normalizers.stock import (
    get_source_priority,
    normalize_cninfo_event,
    normalize_company_profile,
    normalize_financial_summary,
    normalize_price_daily,
    normalize_ticker_input,
)
from app.schemas.stock import (
    CompanyOverview,
    CompanyOverviewCompanySection,
    CompanyOverviewEventsSection,
    CompanyOverviewFinancialSection,
    CompanyOverviewPriceSection,
    CompanyOverviewRiskFlagsSection,
    CompanyOverviewSignalsSection,
    DataStatus,
    EventListDebugResponse,
    EventSourceDebug,
    PriceListDebugResponse,
    PriceSourceDebug,
    RiskFlag,
    StockResearchContext,
    TimelineItem,
    OverviewSignal,
)


class StockDataService:
    def __init__(
        self,
        repository: StockRepository | None = None,
        tushare_collector: TushareCollector | None = None,
        cninfo_collector: CNInfoCollector | None = None,
        exchange_search_collector: ExchangeSearchCollector | None = None,
        akshare_collector: AKShareCollector | None = None,
    ) -> None:
        self.repository = repository or get_repository()
        self.tushare_collector = tushare_collector or TushareCollector()
        self.cninfo_collector = cninfo_collector or CNInfoCollector()
        self.exchange_search_collector = exchange_search_collector or ExchangeSearchCollector()
        self.akshare_collector = akshare_collector or AKShareCollector()

    def get_company(self, ticker: str, refresh: bool = False) -> CompanyProfile:
        company, data_status = self._load_company(normalize_ticker_input(ticker), refresh=refresh)
        if company is not None:
            return company
        raise RuntimeError(data_status.error_message or f"No company profile found for {ticker}")

    def list_events(self, ticker: str, limit: int = 20, refresh: bool = False) -> list[Event]:
        return self.list_events_with_debug(ticker=ticker, limit=limit, refresh=refresh).items

    def list_events_with_debug(self, ticker: str, limit: int = 20, refresh: bool = False) -> EventListDebugResponse:
        normalized = normalize_ticker_input(ticker)
        events, _, debug = self._load_events(normalized, limit=limit, refresh=refresh)
        return EventListDebugResponse(ticker=normalized, items=events, debug=debug)

    def list_financials(self, ticker: str, limit: int = 8, refresh: bool = False) -> list[FinancialSummary]:
        items, _ = self._load_financials(normalize_ticker_input(ticker), limit=limit, refresh=refresh)
        return items

    def list_prices(
        self,
        ticker: str,
        limit: int = 60,
        start_date: str | None = None,
        end_date: str | None = None,
        refresh: bool = False,
    ) -> list[PriceDaily]:
        prices, _, _ = self._load_prices(
            normalize_ticker_input(ticker),
            limit=limit,
            start_date=start_date,
            end_date=end_date,
            refresh=refresh,
        )
        return prices

    def list_prices_with_debug(
        self,
        ticker: str,
        limit: int = 60,
        start_date: str | None = None,
        end_date: str | None = None,
        refresh: bool = False,
    ) -> PriceListDebugResponse:
        normalized = normalize_ticker_input(ticker)
        prices, _, debug = self._load_prices(
            normalized,
            limit=limit,
            start_date=start_date,
            end_date=end_date,
            refresh=refresh,
        )
        return PriceListDebugResponse(ticker=normalized, items=prices, debug=debug)

    def get_overview(self, ticker: str, refresh: bool = False) -> CompanyOverview:
        normalized = normalize_ticker_input(ticker)
        company, company_status = self._load_company(normalized, refresh=refresh)
        financials, financial_status = self._load_financials(normalized, limit=4, refresh=refresh)
        prices, price_status, _ = self._load_prices(normalized, limit=30, refresh=refresh)
        events, event_status, _ = self._load_events(normalized, limit=5, refresh=refresh)
        latest_financial = financials[0] if financials else None
        latest_price = prices[-1] if prices else None
        risk_flags = self.get_risk_flags(ticker, refresh=refresh)
        risk_status = self._build_risk_flags_status(
            financial_status=financial_status,
            price_status=price_status,
            event_status=event_status,
        )
        signals = self._build_overview_signals(
            latest_financial=latest_financial,
            latest_price=latest_price,
            recent_events=events,
            risk_flags=risk_flags,
        )
        return CompanyOverview(
            ticker=normalized,
            company=CompanyOverviewCompanySection(
                data=company or self._build_placeholder_company(normalized),
                data_status=company_status,
            ),
            latest_financial=CompanyOverviewFinancialSection(data=latest_financial, data_status=financial_status),
            latest_price=CompanyOverviewPriceSection(data=latest_price, data_status=price_status),
            recent_events=CompanyOverviewEventsSection(data=events, data_status=event_status),
            risk_flags=CompanyOverviewRiskFlagsSection(data=risk_flags, data_status=risk_status),
            signals=CompanyOverviewSignalsSection(data=signals, data_status=risk_status),
        )

    def get_timeline(self, ticker: str, refresh: bool = False) -> list[TimelineItem]:
        events = self.list_events(ticker, limit=20, refresh=refresh)
        financials = self.list_financials(ticker, limit=8, refresh=refresh)
        prices = self.list_prices(ticker, limit=10, refresh=refresh)
        timeline: list[TimelineItem] = []

        for event in events:
            timeline.append(
                TimelineItem(
                    date=event.event_date or event.updated_at or "",
                    kind="event",
                    title=event.title,
                    summary=event.summary,
                    url=event.url,
                    source=event.source,
                    importance=event.importance or ("high" if event.event_type else "medium"),
                )
            )

        for financial in financials:
            timeline.append(
                TimelineItem(
                    date=financial.announcement_date or financial.report_date,
                    kind="financial",
                    title=f"{financial.report_date} financial summary",
                    summary=self._build_financial_summary_text(financial),
                    source=financial.source,
                    importance=self._financial_importance(financial),
                )
            )

        for price in prices:
            if price.change_pct is None:
                continue
            if abs(price.change_pct) < 2:
                continue
            timeline.append(
                TimelineItem(
                    date=price.trade_date,
                    kind="price",
                    title=f"{price.trade_date} close {price.close}",
                    summary=self._build_price_summary_text(price),
                    source=price.source,
                    importance="high" if abs(price.change_pct) >= 7 else "medium",
                )
            )

        return sorted(timeline, key=lambda item: item.date or "", reverse=True)

    def get_risk_flags(self, ticker: str, refresh: bool = False) -> list[RiskFlag]:
        financials = self.list_financials(ticker, limit=4, refresh=refresh)
        prices = self.list_prices(ticker, limit=30, refresh=refresh)
        events = self.list_events(ticker, limit=10, refresh=refresh)
        flags: list[RiskFlag] = []

        latest_financial = financials[0] if financials else None
        if latest_financial and latest_financial.net_profit is not None and latest_financial.net_profit < 0:
            flags.append(
                RiskFlag(
                    level="high",
                    code="negative_net_profit",
                    message=f"Latest reported net profit is negative ({latest_financial.net_profit}).",
                    dimension="financial",
                    as_of_date=latest_financial.announcement_date or latest_financial.report_date,
                )
            )
        if latest_financial and latest_financial.revenue_yoy is not None and latest_financial.revenue_yoy < 0:
            flags.append(
                RiskFlag(
                    level="medium",
                    code="revenue_yoy_down",
                    message=f"Latest reported revenue growth is negative ({latest_financial.revenue_yoy}%).",
                    dimension="financial",
                    as_of_date=latest_financial.announcement_date or latest_financial.report_date,
                )
            )
        if latest_financial and latest_financial.net_profit_yoy is not None and latest_financial.net_profit_yoy < 0:
            flags.append(
                RiskFlag(
                    level="medium",
                    code="profit_yoy_down",
                    message=f"Latest reported profit growth is negative ({latest_financial.net_profit_yoy}%).",
                    dimension="financial",
                    as_of_date=latest_financial.announcement_date or latest_financial.report_date,
                )
            )
        if latest_financial and latest_financial.gross_margin is not None and latest_financial.gross_margin < 15:
            flags.append(
                RiskFlag(
                    level="medium",
                    code="low_gross_margin",
                    message=f"Latest gross margin is relatively low ({latest_financial.gross_margin}%).",
                    dimension="financial",
                    as_of_date=latest_financial.announcement_date or latest_financial.report_date,
                )
            )
        if latest_financial is None:
            flags.append(
                RiskFlag(
                    level="medium",
                    code="financial_data_unavailable",
                    message="No recent financial summary is available.",
                    dimension="financial",
                )
            )

        if len(prices) >= 5:
            recent_changes = [abs(item.change_pct or 0) for item in prices[-5:]]
            if max(recent_changes) >= 9:
                flags.append(
                    RiskFlag(
                        level="medium",
                        code="price_volatility",
                        message="Recent daily price swings exceeded 9%.",
                        dimension="price",
                        as_of_date=prices[-1].trade_date,
                    )
                )
            closes = [item.close for item in prices if item.close is not None]
            if closes:
                max_close = max(closes)
                latest_close = closes[-1]
                drawdown_pct = ((latest_close / max_close) - 1) * 100 if max_close else 0
                if drawdown_pct <= -10:
                    flags.append(
                        RiskFlag(
                            level="medium",
                            code="recent_drawdown",
                            message=f"Latest close is {abs(round(drawdown_pct, 2))}% below the recent high.",
                            dimension="price",
                            as_of_date=prices[-1].trade_date,
                        )
                    )
        elif not prices:
            flags.append(
                RiskFlag(
                    level="low",
                    code="price_data_unavailable",
                    message="No recent daily price data is available.",
                    dimension="price",
                )
            )

        if events:
            latest_event_date = max((event.event_date or "" for event in events), default="")
            if latest_event_date:
                flags.append(
                    RiskFlag(
                        level="low",
                        code="recent_disclosures_available",
                        message=f"Recent disclosure data is available up to {latest_event_date}.",
                        dimension="event",
                        as_of_date=latest_event_date,
                    )
                )
            if any("风险" in (event.title or "") or "问询" in (event.title or "") for event in events):
                flags.append(
                    RiskFlag(
                        level="medium",
                        code="risk_related_disclosure",
                        message="Recent disclosures include risk or inquiry-related wording.",
                        dimension="event",
                        as_of_date=latest_event_date or None,
                    )
                )
        else:
            flags.append(
                RiskFlag(
                    level="low",
                    code="event_data_unavailable",
                    message="No recent disclosure events are available.",
                    dimension="event",
                )
            )

        return flags

    def get_research_context(self, ticker: str, refresh: bool = False) -> StockResearchContext:
        overview = self.get_overview(ticker, refresh=refresh)
        return StockResearchContext(
            ticker=overview.ticker,
            company=overview.company.data,
            recent_events=overview.recent_events.data,
            latest_financial=overview.latest_financial.data,
            latest_price=overview.latest_price.data,
            risk_flags=overview.risk_flags.data,
        )

    def _load_company(self, ticker: str, refresh: bool = False) -> tuple[CompanyProfile | None, DataStatus]:
        cached = self.repository.get_company_profile(ticker)
        last_synced_at = self.repository.get_last_synced_at("company_profile", ticker)
        if cached and not self._should_refresh("company_profile", ticker, refresh):
            return cached, self._build_data_status(
                source=cached.source,
                updated_at=cached.updated_at or last_synced_at,
                cache_hit=True,
            )

        try:
            raw = self.tushare_collector.fetch_company_profile(ticker)
        except RuntimeError as exc:
            if cached:
                return cached, self._build_data_status(
                    source=cached.source,
                    updated_at=cached.updated_at or last_synced_at,
                    cache_hit=True,
                    error_message=str(exc),
                )
            return None, self._build_data_status(
                source="tushare",
                updated_at=last_synced_at,
                error_message=str(exc),
                failed=True,
            )

        if raw:
            profile = self.repository.upsert_company_profile(normalize_company_profile(ticker, raw))
            return profile, self._build_data_status(source=profile.source, updated_at=profile.updated_at, cache_hit=False)

        if cached:
            return cached, self._build_data_status(
                source=cached.source,
                updated_at=cached.updated_at or last_synced_at,
                cache_hit=True,
                error_message="Upstream returned empty company profile.",
            )
        return None, self._build_data_status(source="tushare", updated_at=None, cache_hit=False, missing=True)

    def _load_financials(
        self,
        ticker: str,
        limit: int = 8,
        refresh: bool = False,
    ) -> tuple[list[FinancialSummary], DataStatus]:
        cached = self.repository.list_financial_summaries(ticker, limit=limit)
        last_synced_at = self.repository.get_last_synced_at("financial_summary", ticker)
        if cached and not self._should_refresh("financial_summary", ticker, refresh):
            return cached, self._build_data_status(
                source=cached[0].source,
                updated_at=last_synced_at or cached[0].updated_at,
                cache_hit=True,
            )

        try:
            raw_items = self.tushare_collector.fetch_financial_summaries(ticker, limit=limit)
        except RuntimeError as exc:
            if cached:
                return cached, self._build_data_status(
                    source=cached[0].source,
                    updated_at=last_synced_at or cached[0].updated_at,
                    cache_hit=True,
                    error_message=str(exc),
                )
            return [], self._build_data_status(
                source="tushare",
                updated_at=last_synced_at,
                error_message=str(exc),
                failed=True,
            )

        items = [normalize_financial_summary(ticker, raw) for raw in raw_items]
        if items:
            stored = self.repository.upsert_financial_summaries(ticker, items)
            latest = self.repository.list_financial_summaries(ticker, limit=limit) or stored
            return latest, self._build_data_status(
                source=latest[0].source,
                updated_at=latest[0].updated_at or last_synced_at,
                cache_hit=False,
            )
        if cached:
            return cached, self._build_data_status(
                source=cached[0].source,
                updated_at=last_synced_at or cached[0].updated_at,
                cache_hit=True,
                error_message="Upstream returned empty financial summaries.",
            )
        return [], self._build_data_status(source="tushare", updated_at=None, cache_hit=False, missing=True)

    def _load_prices(
        self,
        ticker: str,
        limit: int = 60,
        start_date: str | None = None,
        end_date: str | None = None,
        refresh: bool = False,
    ) -> tuple[list[PriceDaily], DataStatus, list[PriceSourceDebug]]:
        cached = self.repository.list_prices(ticker, limit=limit, start_date=start_date, end_date=end_date)
        last_synced_at = self.repository.get_last_synced_at("price_daily", ticker)
        if cached and not self._should_refresh("price_daily", ticker, refresh):
            items = list(reversed(cached))
            return items, self._build_data_status(
                source=items[-1].source,
                updated_at=last_synced_at or items[-1].updated_at,
                cache_hit=True,
            ), [PriceSourceDebug(source="cache", status="hit", count=len(items))]

        debug: list[PriceSourceDebug] = []
        raw_prices: list[dict] = []
        last_error: str | None = None
        for source_name, collector in (
            ("akshare", self.akshare_collector.fetch_daily_prices),
            ("tushare", self.tushare_collector.fetch_daily_prices),
        ):
            try:
                raw_prices = collector(ticker, limit=limit, start_date=start_date, end_date=end_date)
                debug.append(PriceSourceDebug(source=source_name, status="ok" if raw_prices else "empty", count=len(raw_prices)))
            except RuntimeError as exc:
                last_error = str(exc)
                debug.append(PriceSourceDebug(source=source_name, status="error", count=0, error=last_error))
                raw_prices = []
            if raw_prices:
                break

        prices = [normalize_price_daily(ticker, raw) for raw in raw_prices]
        if prices:
            self.repository.upsert_prices(ticker, prices)
            latest = list(reversed(self.repository.list_prices(ticker, limit=limit, start_date=start_date, end_date=end_date)))
            return latest, self._build_data_status(
                source=latest[-1].source,
                updated_at=last_synced_at or latest[-1].updated_at,
                cache_hit=False,
            ), debug
        if cached:
            items = list(reversed(cached))
            return items, self._build_data_status(
                source=items[-1].source,
                updated_at=last_synced_at or items[-1].updated_at,
                cache_hit=True,
                error_message=last_error or "Upstream returned empty price rows.",
            ), debug
        if last_error:
            return [], self._build_data_status(
                source="akshare",
                updated_at=last_synced_at,
                error_message=last_error,
                failed=True,
            ), debug
        return [], self._build_data_status(source=None, updated_at=None, cache_hit=False, missing=True), debug

    def _load_events(
        self,
        ticker: str,
        limit: int = 20,
        refresh: bool = False,
    ) -> tuple[list[Event], DataStatus, list[EventSourceDebug]]:
        cached = self.repository.list_events(ticker, limit=limit)
        last_synced_at = self.repository.get_last_synced_at("event", ticker)
        if cached and not self._should_refresh("event", ticker, refresh):
            return cached, self._build_data_status(
                source=cached[0].source,
                updated_at=last_synced_at or cached[0].updated_at,
                cache_hit=True,
            ), [EventSourceDebug(source="cache", status="hit", count=len(cached), kept_count=len(cached))]

        debug: list[EventSourceDebug] = []
        collected: list[Event] = []
        error_message: str | None = None
        try:
            cninfo_raw = self.cninfo_collector.fetch_events(ticker, limit=limit)
            normalized_events = [normalize_cninfo_event(ticker, raw) for raw in cninfo_raw]
            collected.extend(normalized_events)
            debug.append(
                EventSourceDebug(
                    source="cninfo",
                    status="ok" if cninfo_raw else "empty",
                    count=len(cninfo_raw),
                    kept_count=len(normalized_events),
                )
            )
        except RuntimeError as exc:
            error_message = str(exc)
            debug.append(EventSourceDebug(source="cninfo", status="error", count=0, kept_count=0, error=error_message))

        company_name = None
        if not collected:
            company, _ = self._load_company(ticker, refresh=refresh)
            company_name = company.name if company else None
            try:
                fallback_payload = self.exchange_search_collector.fetch_events_with_debug(
                    ticker,
                    company_name=company_name,
                    limit=limit,
                )
                fallback_events = [Event(**item) for item in fallback_payload["items"]]
                collected.extend(fallback_events)
                debug.append(EventSourceDebug(**fallback_payload["debug"]))
            except RuntimeError as exc:
                error_message = str(exc)
                debug.append(
                    EventSourceDebug(
                        source="exchange_search",
                        status="error",
                        count=0,
                        kept_count=0,
                        error=error_message,
                    )
                )

        deduped = self._dedupe_events(collected, limit=limit)
        if deduped:
            if refresh:
                self.repository.replace_events(ticker, deduped)
            else:
                self.repository.upsert_events(ticker, deduped)
            latest = self.repository.list_events(ticker, limit=limit)
            return latest, self._build_data_status(
                source=latest[0].source,
                updated_at=last_synced_at or latest[0].updated_at,
                cache_hit=False,
                error_message=error_message,
            ), debug
        if cached:
            return cached, self._build_data_status(
                source=cached[0].source,
                updated_at=last_synced_at or cached[0].updated_at,
                cache_hit=True,
                error_message=error_message or "No upstream event rows returned.",
            ), debug
        if error_message:
            return [], self._build_data_status(
                source="cninfo",
                updated_at=last_synced_at,
                error_message=error_message,
                failed=True,
            ), debug
        return [], self._build_data_status(source=None, updated_at=None, cache_hit=False, missing=True), debug

    def _should_refresh(self, dataset: str, ticker: str, force_refresh: bool) -> bool:
        if force_refresh:
            return True
        last_synced_at = self.repository.get_last_synced_at(dataset, ticker)
        if not last_synced_at:
            return True
        try:
            synced_at = datetime.fromisoformat(last_synced_at.replace("Z", "+00:00"))
        except ValueError:
            return True
        ttl = timedelta(hours=settings.stock_data_ttl_hours)
        return synced_at + ttl <= datetime.now(timezone.utc)

    def _is_stale(self, updated_at: str | None) -> bool:
        if not updated_at:
            return True
        try:
            synced_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        except ValueError:
            return True
        return synced_at + timedelta(hours=settings.stock_data_ttl_hours) <= datetime.now(timezone.utc)

    def _build_financial_summary_text(self, item: FinancialSummary) -> str:
        parts = [
            f"revenue={item.revenue}" if item.revenue is not None else None,
            f"revenue_yoy={item.revenue_yoy}%" if item.revenue_yoy is not None else None,
            f"net_profit={item.net_profit}" if item.net_profit is not None else None,
            f"net_profit_yoy={item.net_profit_yoy}%" if item.net_profit_yoy is not None else None,
            f"eps={item.eps}" if item.eps is not None else None,
            f"gross_margin={item.gross_margin}%" if item.gross_margin is not None else None,
        ]
        return ", ".join(part for part in parts if part)

    def _build_price_summary_text(self, item: PriceDaily) -> str:
        parts = [
            f"pct_change={item.change_pct}%" if item.change_pct is not None else None,
            f"turnover={item.turnover_rate}%" if item.turnover_rate is not None else None,
            f"range={item.low}-{item.high}" if item.low is not None and item.high is not None else None,
        ]
        return ", ".join(part for part in parts if part)

    def _financial_importance(self, item: FinancialSummary) -> str:
        if item.net_profit is not None and item.net_profit < 0:
            return "high"
        if item.revenue_yoy is not None and abs(item.revenue_yoy) >= 20:
            return "high"
        return "medium"

    def _build_placeholder_company(self, ticker: str) -> CompanyProfile:
        return CompanyProfile(
            ticker=ticker,
            source="fallback",
            dedupe_key=ticker,
            source_priority=get_source_priority("fallback"),
            status="unknown",
            raw={},
        )

    def _build_data_status(
        self,
        source: str | None,
        updated_at: str | None,
        cache_hit: bool,
        error_message: str | None = None,
        missing: bool = False,
        failed: bool = False,
    ) -> DataStatus:
        if failed:
            status = "failed"
        elif missing or source is None:
            status = "missing"
        elif self._is_stale(updated_at):
            status = "stale"
        else:
            status = "fresh"
        return DataStatus(
            status=status,
            updated_at=updated_at,
            source=source,
            ttl_hours=settings.stock_data_ttl_hours,
            cache_hit=cache_hit,
            error_message=error_message,
        )

    def _build_risk_flags_status(
        self,
        financial_status: DataStatus,
        price_status: DataStatus,
        event_status: DataStatus,
    ) -> DataStatus:
        component_statuses = [financial_status.status, price_status.status, event_status.status]
        updated_candidates = [status.updated_at for status in (financial_status, price_status, event_status) if status.updated_at]
        if all(status == "missing" for status in component_statuses):
            status = "missing"
        elif "failed" in component_statuses:
            status = "failed"
        elif "stale" in component_statuses:
            status = "stale"
        else:
            status = "fresh"
        return DataStatus(
            status=status,
            updated_at=max(updated_candidates) if updated_candidates else None,
            source="derived",
            ttl_hours=settings.stock_data_ttl_hours,
            cache_hit=True,
            error_message=None,
        )

    def _dedupe_events(self, events: list[Event], limit: int) -> list[Event]:
        deduped: dict[str, Event] = {}
        for event in events:
            key = event.dedupe_key or event.event_id
            existing = deduped.get(key)
            if existing is None:
                deduped[key] = event
                continue
            if event.source_priority > existing.source_priority:
                deduped[key] = event
                continue
            if event.source_priority == existing.source_priority and (event.updated_at or "") > (existing.updated_at or ""):
                deduped[key] = event
        return sorted(
            deduped.values(),
            key=lambda item: ((item.event_date or ""), item.importance or "", item.updated_at or ""),
            reverse=True,
        )[:limit]

    def _build_overview_signals(
        self,
        latest_financial: FinancialSummary | None,
        latest_price: PriceDaily | None,
        recent_events: list[Event],
        risk_flags: list[RiskFlag],
    ) -> list[OverviewSignal]:
        signals: list[OverviewSignal] = []
        if latest_financial:
            direction = "negative" if (latest_financial.net_profit or 0) < 0 else "positive"
            value = "negative" if direction == "negative" else "positive"
            evidence = (
                "Latest reported net profit is below zero."
                if direction == "negative"
                else "Latest reported net profit is positive."
            )
            signals.append(
                OverviewSignal(
                    code="profitability",
                    label="Profitability",
                    value=value,
                    importance="high" if direction == "negative" else "medium",
                    direction=direction,
                    evidence=evidence,
                )
            )
        if latest_price and latest_price.change_pct is not None:
            direction = "positive" if latest_price.change_pct > 0 else "negative" if latest_price.change_pct < 0 else "neutral"
            signals.append(
                OverviewSignal(
                    code="latest_price_move",
                    label="Latest Price Move",
                    value=f"{latest_price.change_pct}%",
                    importance="high" if abs(latest_price.change_pct) >= 7 else "medium",
                    direction=direction,
                    evidence=f"Latest daily change_pct is {latest_price.change_pct}%.",
                )
            )
        if recent_events:
            signals.append(
                OverviewSignal(
                    code="disclosure_activity",
                    label="Disclosure Activity",
                    value=str(len(recent_events)),
                    importance="medium" if len(recent_events) >= 3 else "low",
                    direction="neutral",
                    evidence=f"{len(recent_events)} recent disclosure events are available.",
                )
            )
        if risk_flags:
            highest_level = "high" if any(flag.level == "high" for flag in risk_flags) else "medium" if any(flag.level == "medium" for flag in risk_flags) else "low"
            signals.append(
                OverviewSignal(
                    code="risk_flag_pressure",
                    label="Risk Flag Pressure",
                    value=highest_level,
                    importance=highest_level,
                    direction="negative" if highest_level in {"high", "medium"} else "neutral",
                    evidence=f"{len(risk_flags)} risk flags generated from current data.",
                )
            )
        return signals


_stock_data_service: StockDataService | None = None


def get_stock_data_service() -> StockDataService:
    global _stock_data_service
    if _stock_data_service is None:
        _stock_data_service = StockDataService()
    return _stock_data_service
