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
    CompanyDebugResponse,
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
    FinancialListDebugResponse,
    OverviewDebugResponse,
    PriceListDebugResponse,
    PriceSourceDebug,
    RiskFlag,
    StockEndpointDebug,
    StockSectionDebug,
    SourceMetadata,
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

    def get_company_with_debug(self, ticker: str, refresh: bool = False) -> CompanyDebugResponse:
        normalized = normalize_ticker_input(ticker)
        company, data_status = self._load_company(normalized, refresh=refresh)
        return CompanyDebugResponse(
            ticker=normalized,
            data=company,
            data_status=data_status,
            debug=self._build_endpoint_debug(
                endpoint="company_profile",
                data_status=data_status,
                sources=self._build_data_status_sources_debug(data_status, item_count=1 if company else 0),
            ),
        )

    def list_events(self, ticker: str, limit: int = 20, refresh: bool = False) -> list[Event]:
        return self.list_events_with_debug(ticker=ticker, limit=limit, refresh=refresh).items

    def list_events_with_debug(self, ticker: str, limit: int = 20, refresh: bool = False) -> EventListDebugResponse:
        normalized = normalize_ticker_input(ticker)
        events, data_status, debug = self._load_events(normalized, limit=limit, refresh=refresh)
        return EventListDebugResponse(
            ticker=normalized,
            items=events,
            data_status=data_status,
            debug=self._build_endpoint_debug(endpoint="event", data_status=data_status, sources=debug),
        )

    def list_financials(self, ticker: str, limit: int = 8, refresh: bool = False) -> list[FinancialSummary]:
        items, _ = self._load_financials(normalize_ticker_input(ticker), limit=limit, refresh=refresh)
        return items

    def list_financials_with_debug(self, ticker: str, limit: int = 8, refresh: bool = False) -> FinancialListDebugResponse:
        normalized = normalize_ticker_input(ticker)
        items, data_status = self._load_financials(normalized, limit=limit, refresh=refresh)
        return FinancialListDebugResponse(
            ticker=normalized,
            items=items,
            data_status=data_status,
            debug=self._build_endpoint_debug(
                endpoint="financial_summary",
                data_status=data_status,
                sources=self._build_data_status_sources_debug(data_status, item_count=len(items)),
            ),
        )

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
        prices, data_status, debug = self._load_prices(
            normalized,
            limit=limit,
            start_date=start_date,
            end_date=end_date,
            refresh=refresh,
        )
        return PriceListDebugResponse(
            ticker=normalized,
            items=prices,
            data_status=data_status,
            debug=self._build_endpoint_debug(endpoint="price_daily", data_status=data_status, sources=debug),
        )

    def get_overview(self, ticker: str, refresh: bool = False) -> CompanyOverview:
        return self.get_overview_with_debug(ticker, refresh=refresh).data

    def get_overview_with_debug(self, ticker: str, refresh: bool = False) -> OverviewDebugResponse:
        normalized = normalize_ticker_input(ticker)
        company, company_status = self._load_company(normalized, refresh=refresh)
        financials, financial_status = self._load_financials(normalized, limit=4, refresh=refresh)
        prices, price_status, price_debug = self._load_prices(normalized, limit=30, refresh=refresh)
        events, event_status, event_debug = self._load_events(normalized, limit=5, refresh=refresh)
        latest_financial = financials[0] if financials else None
        latest_price = prices[-1] if prices else None
        risk_flags = self._build_risk_flags(financials=financials, prices=prices, events=events)
        risk_status = self._build_risk_flags_status(
            financial_status=financial_status,
            price_status=price_status,
            event_status=event_status,
        )
        signals_status = self._build_signals_status(risk_status=risk_status)
        signals = self._build_overview_signals(
            latest_financial=latest_financial,
            latest_price=latest_price,
            recent_events=events,
            risk_flags=risk_flags,
        )
        overview_status = self._build_overview_status(
            company_status=company_status,
            financial_status=financial_status,
            price_status=price_status,
            event_status=event_status,
            risk_status=risk_status,
        )
        overview = CompanyOverview(
            ticker=normalized,
            company=CompanyOverviewCompanySection(
                data=company or self._build_placeholder_company(normalized),
                data_status=company_status,
            ),
            latest_financial=CompanyOverviewFinancialSection(data=latest_financial, data_status=financial_status),
            latest_price=CompanyOverviewPriceSection(data=latest_price, data_status=price_status),
            recent_events=CompanyOverviewEventsSection(data=events, data_status=event_status),
            risk_flags=CompanyOverviewRiskFlagsSection(data=risk_flags, data_status=risk_status),
            signals=CompanyOverviewSignalsSection(data=signals, data_status=signals_status),
        )
        return OverviewDebugResponse(
            ticker=normalized,
            data=overview,
            data_status=overview_status,
            debug=self._build_endpoint_debug(
                endpoint="company_overview",
                data_status=overview_status,
                sections={
                    "company": self._build_section_debug(company_status, self._build_data_status_sources_debug(company_status, item_count=1 if company else 0)),
                    "latest_financial": self._build_section_debug(financial_status, self._build_data_status_sources_debug(financial_status, item_count=1 if latest_financial else 0)),
                    "latest_price": self._build_section_debug(price_status, price_debug),
                    "recent_events": self._build_section_debug(event_status, event_debug),
                    "risk_flags": self._build_section_debug(risk_status, self._build_data_status_sources_debug(risk_status, item_count=len(risk_flags))),
                    "signals": self._build_section_debug(signals_status, self._build_data_status_sources_debug(signals_status, item_count=len(signals))),
                },
            ),
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
        return self._build_risk_flags(financials=financials, prices=prices, events=events)

    def _build_risk_flags(
        self,
        *,
        financials: list[FinancialSummary],
        prices: list[PriceDaily],
        events: list[Event],
    ) -> list[RiskFlag]:
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
        started_at = self._now()
        cached = self.repository.get_company_profile(ticker)
        sync_state = self._get_sync_state("company_profile", ticker)
        last_synced_at = self._sync_state_value(sync_state, "last_synced_at")
        if cached and not self._should_refresh("company_profile", ticker, refresh):
            return cached, self._build_data_status(
                source=cached.source,
                updated_at=cached.updated_at or last_synced_at,
                cache_hit=True,
                sync_state=sync_state,
                source_metadata=self._build_source_metadata(cached.source, attempted_sources=["tushare"]),
            )

        try:
            raw = self.tushare_collector.fetch_company_profile(ticker)
        except RuntimeError as exc:
            self._record_dataset_sync(
                "company_profile",
                ticker,
                success=False,
                error_message=str(exc),
                started_at=started_at,
            )
            sync_state = self._get_sync_state("company_profile", ticker)
            if cached:
                return cached, self._build_data_status(
                    source=cached.source,
                    updated_at=cached.updated_at or last_synced_at,
                    cache_hit=True,
                    error_message=str(exc),
                    sync_state=sync_state,
                    source_metadata=self._build_source_metadata(cached.source, attempted_sources=["tushare"]),
                )
            return None, self._build_data_status(
                source="tushare",
                updated_at=last_synced_at,
                error_message=str(exc),
                failed=True,
                sync_state=sync_state,
                source_metadata=self._build_source_metadata("tushare", attempted_sources=["tushare"]),
            )

        if raw:
            profile = self.repository.upsert_company_profile(normalize_company_profile(ticker, raw))
            self._record_dataset_sync(
                "company_profile",
                ticker,
                success=True,
                records_written=1,
                started_at=started_at,
            )
            return profile, self._build_data_status(
                source=profile.source,
                updated_at=profile.updated_at,
                cache_hit=False,
                sync_state=self._get_sync_state("company_profile", ticker),
                source_metadata=self._build_source_metadata(profile.source, attempted_sources=["tushare"]),
            )

        self._record_dataset_sync("company_profile", ticker, success=True, records_written=0, started_at=started_at)
        sync_state = self._get_sync_state("company_profile", ticker)
        if cached:
            return cached, self._build_data_status(
                source=cached.source,
                updated_at=cached.updated_at or last_synced_at,
                cache_hit=True,
                error_message="Upstream returned empty company profile.",
                sync_state=sync_state,
                source_metadata=self._build_source_metadata(cached.source, attempted_sources=["tushare"]),
            )
        return None, self._build_data_status(
            source="tushare",
            updated_at=None,
            cache_hit=False,
            missing=True,
            sync_state=sync_state,
            source_metadata=self._build_source_metadata("tushare", attempted_sources=["tushare"]),
        )

    def _load_financials(
        self,
        ticker: str,
        limit: int = 8,
        refresh: bool = False,
    ) -> tuple[list[FinancialSummary], DataStatus]:
        started_at = self._now()
        cached = self.repository.list_financial_summaries(ticker, limit=limit)
        sync_state = self._get_sync_state("financial_summary", ticker)
        last_synced_at = self._sync_state_value(sync_state, "last_synced_at")
        if cached and not self._should_refresh("financial_summary", ticker, refresh):
            return cached, self._build_data_status(
                source=cached[0].source,
                updated_at=last_synced_at or cached[0].updated_at,
                cache_hit=True,
                sync_state=sync_state,
                source_metadata=self._build_source_metadata(cached[0].source, attempted_sources=["tushare"]),
            )

        try:
            raw_items = self.tushare_collector.fetch_financial_summaries(ticker, limit=limit)
        except RuntimeError as exc:
            self._record_dataset_sync(
                "financial_summary",
                ticker,
                success=False,
                error_message=str(exc),
                started_at=started_at,
            )
            sync_state = self._get_sync_state("financial_summary", ticker)
            if cached:
                return cached, self._build_data_status(
                    source=cached[0].source,
                    updated_at=last_synced_at or cached[0].updated_at,
                    cache_hit=True,
                    error_message=str(exc),
                    sync_state=sync_state,
                    source_metadata=self._build_source_metadata(cached[0].source, attempted_sources=["tushare"]),
                )
            return [], self._build_data_status(
                source="tushare",
                updated_at=last_synced_at,
                error_message=str(exc),
                failed=True,
                sync_state=sync_state,
                source_metadata=self._build_source_metadata("tushare", attempted_sources=["tushare"]),
            )

        items = [normalize_financial_summary(ticker, raw) for raw in raw_items]
        if items:
            stored = self.repository.upsert_financial_summaries(ticker, items)
            self._record_dataset_sync(
                "financial_summary",
                ticker,
                success=True,
                records_written=len(items),
                started_at=started_at,
            )
            latest = self.repository.list_financial_summaries(ticker, limit=limit) or stored
            return latest, self._build_data_status(
                source=latest[0].source,
                updated_at=latest[0].updated_at or last_synced_at,
                cache_hit=False,
                sync_state=self._get_sync_state("financial_summary", ticker),
                source_metadata=self._build_source_metadata(latest[0].source, attempted_sources=["tushare"]),
            )
        self._record_dataset_sync("financial_summary", ticker, success=True, records_written=0, started_at=started_at)
        sync_state = self._get_sync_state("financial_summary", ticker)
        if cached:
            return cached, self._build_data_status(
                source=cached[0].source,
                updated_at=last_synced_at or cached[0].updated_at,
                cache_hit=True,
                error_message="Upstream returned empty financial summaries.",
                sync_state=sync_state,
                source_metadata=self._build_source_metadata(cached[0].source, attempted_sources=["tushare"]),
            )
        return [], self._build_data_status(
            source="tushare",
            updated_at=None,
            cache_hit=False,
            missing=True,
            sync_state=sync_state,
            source_metadata=self._build_source_metadata("tushare", attempted_sources=["tushare"]),
        )

    def _load_prices(
        self,
        ticker: str,
        limit: int = 60,
        start_date: str | None = None,
        end_date: str | None = None,
        refresh: bool = False,
    ) -> tuple[list[PriceDaily], DataStatus, list[PriceSourceDebug]]:
        started_at = self._now()
        cached = self.repository.list_prices(ticker, limit=limit, start_date=start_date, end_date=end_date)
        sync_state = self._get_sync_state("price_daily", ticker)
        last_synced_at = self._sync_state_value(sync_state, "last_synced_at")
        if cached and not self._should_refresh("price_daily", ticker, refresh):
            items = list(reversed(cached))
            return items, self._build_data_status(
                source=items[-1].source,
                updated_at=last_synced_at or items[-1].updated_at,
                cache_hit=True,
                sync_state=sync_state,
                source_metadata=self._build_source_metadata(
                    items[-1].source,
                    attempted_sources=["cache"],
                    returned_sources=[items[-1].source],
                    selection_reason="cache_hit",
                ),
            ), [PriceSourceDebug(source="cache", status="hit", count=len(items), kept_count=len(items))]

        debug: list[PriceSourceDebug] = []
        raw_prices_by_source: dict[str, list[dict]] = {}
        last_error: str | None = None
        for source_name, collector in (
            ("akshare", self.akshare_collector.fetch_daily_prices),
            ("tushare", self.tushare_collector.fetch_daily_prices),
        ):
            try:
                raw_prices = collector(ticker, limit=limit, start_date=start_date, end_date=end_date)
                raw_prices_by_source[source_name] = raw_prices
                debug.append(
                    PriceSourceDebug(
                        source=source_name,
                        status="ok" if raw_prices else "empty",
                        count=len(raw_prices),
                        kept_count=len(raw_prices),
                    )
                )
            except RuntimeError as exc:
                last_error = str(exc)
                debug.append(PriceSourceDebug(source=source_name, status="error", count=0, kept_count=0, error=last_error))
        selected_source = self._select_runtime_source(
            [source_name for source_name, rows in raw_prices_by_source.items() if rows]
        )
        prices = [normalize_price_daily(ticker, raw) for raw in raw_prices_by_source.get(selected_source, [])]
        if prices:
            self.repository.upsert_prices(ticker, prices)
            self._record_dataset_sync(
                "price_daily",
                ticker,
                success=True,
                error_message=last_error,
                records_written=len(prices),
                started_at=started_at,
            )
            latest = list(reversed(self.repository.list_prices(ticker, limit=limit, start_date=start_date, end_date=end_date)))
            selected_source = latest[-1].source if latest else selected_source
            attempted_sources = [item.source for item in debug]
            returned_sources = list(raw_prices_by_source)
            return latest, self._build_data_status(
                source=selected_source,
                updated_at=latest[-1].updated_at or self._sync_state_value(self._get_sync_state("price_daily", ticker), "last_synced_at"),
                cache_hit=False,
                error_message=last_error,
                partial=bool(last_error),
                sync_state=self._get_sync_state("price_daily", ticker),
                source_metadata=self._build_source_metadata(
                    selected_source,
                    attempted_sources=attempted_sources,
                    returned_sources=returned_sources,
                    fallback_used=bool(selected_source and attempted_sources and selected_source != attempted_sources[0]),
                    selection_reason="highest_source_priority",
                    fallback_reason=self._build_fallback_reason(
                        selected_source=selected_source,
                        attempted_sources=attempted_sources,
                        returned_sources=returned_sources,
                    ),
                ),
            ), debug
        if cached:
            self._record_dataset_sync(
                "price_daily",
                ticker,
                success=False,
                error_message=last_error or "Upstream returned empty price rows.",
                started_at=started_at,
            )
            sync_state = self._get_sync_state("price_daily", ticker)
            items = list(reversed(cached))
            return items, self._build_data_status(
                source=items[-1].source,
                updated_at=last_synced_at or items[-1].updated_at,
                cache_hit=True,
                error_message=last_error or "Upstream returned empty price rows.",
                partial=True,
                sync_state=sync_state,
                source_metadata=self._build_source_metadata(
                    items[-1].source,
                    attempted_sources=[item.source for item in debug],
                    returned_sources=[items[-1].source],
                    fallback_used=True,
                    selection_reason="cache_fallback_after_upstream_failure",
                    fallback_reason=last_error or "Upstream returned empty price rows.",
                ),
            ), debug
        if last_error:
            self._record_dataset_sync(
                "price_daily",
                ticker,
                success=False,
                error_message=last_error,
                started_at=started_at,
            )
            sync_state = self._get_sync_state("price_daily", ticker)
            return [], self._build_data_status(
                source="akshare",
                updated_at=last_synced_at,
                error_message=last_error,
                failed=True,
                sync_state=sync_state,
                source_metadata=self._build_source_metadata(
                    "akshare",
                    attempted_sources=[item.source for item in debug],
                    selection_reason="upstream_failure",
                    fallback_reason=last_error,
                ),
            ), debug
        self._record_dataset_sync("price_daily", ticker, success=True, records_written=0, started_at=started_at)
        sync_state = self._get_sync_state("price_daily", ticker)
        return [], self._build_data_status(
            source=None,
            updated_at=None,
            cache_hit=False,
            missing=True,
            sync_state=sync_state,
            source_metadata=self._build_source_metadata(
                None,
                attempted_sources=[item.source for item in debug],
                selection_reason="no_source_returned_data",
            ),
        ), debug

    def _load_events(
        self,
        ticker: str,
        limit: int = 20,
        refresh: bool = False,
    ) -> tuple[list[Event], DataStatus, list[EventSourceDebug]]:
        started_at = self._now()
        cached = self.repository.list_events(ticker, limit=limit)
        sync_state = self._get_sync_state("event", ticker)
        last_synced_at = self._sync_state_value(sync_state, "last_synced_at")
        if cached and not self._should_refresh("event", ticker, refresh):
            return cached, self._build_data_status(
                source=cached[0].source,
                updated_at=last_synced_at or cached[0].updated_at,
                cache_hit=True,
                sync_state=sync_state,
                source_metadata=self._build_source_metadata(
                    cached[0].source,
                    attempted_sources=["cache"],
                    returned_sources=self._event_sources(cached),
                    selection_reason="cache_hit",
                ),
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
            self._record_dataset_sync(
                "event",
                ticker,
                success=True,
                error_message=error_message,
                records_written=len(deduped),
                started_at=started_at,
            )
            latest = self.repository.list_events(ticker, limit=limit)
            selected_source = self._select_primary_event_source(latest) if latest else None
            attempted_sources = [item.source for item in debug]
            returned_sources = self._event_sources(latest)
            return latest, self._build_data_status(
                source=selected_source,
                updated_at=latest[0].updated_at or self._sync_state_value(self._get_sync_state("event", ticker), "last_synced_at"),
                cache_hit=False,
                error_message=error_message,
                partial=bool(error_message),
                sync_state=self._get_sync_state("event", ticker),
                source_metadata=self._build_source_metadata(
                    selected_source,
                    attempted_sources=attempted_sources,
                    returned_sources=returned_sources,
                    fallback_used=bool(selected_source and attempted_sources and selected_source != attempted_sources[0]),
                    selection_reason="event_dedupe_by_source_priority",
                    fallback_reason=self._build_fallback_reason(
                        selected_source=selected_source,
                        attempted_sources=attempted_sources,
                        returned_sources=returned_sources,
                        error_message=error_message,
                    ),
                ),
            ), debug
        if cached:
            self._record_dataset_sync(
                "event",
                ticker,
                success=False,
                error_message=error_message or "No upstream event rows returned.",
                started_at=started_at,
            )
            sync_state = self._get_sync_state("event", ticker)
            return cached, self._build_data_status(
                source=cached[0].source,
                updated_at=last_synced_at or cached[0].updated_at,
                cache_hit=True,
                error_message=error_message or "No upstream event rows returned.",
                partial=True,
                sync_state=sync_state,
                source_metadata=self._build_source_metadata(
                    cached[0].source,
                    attempted_sources=[item.source for item in debug],
                    returned_sources=self._event_sources(cached),
                    fallback_used=True,
                    selection_reason="cache_fallback_after_upstream_failure",
                    fallback_reason=error_message or "No upstream event rows returned.",
                ),
            ), debug
        if error_message:
            self._record_dataset_sync(
                "event",
                ticker,
                success=False,
                error_message=error_message,
                started_at=started_at,
            )
            sync_state = self._get_sync_state("event", ticker)
            return [], self._build_data_status(
                source="cninfo",
                updated_at=last_synced_at,
                error_message=error_message,
                failed=True,
                sync_state=sync_state,
                source_metadata=self._build_source_metadata(
                    "cninfo",
                    attempted_sources=[item.source for item in debug],
                    selection_reason="upstream_failure",
                    fallback_reason=error_message,
                ),
            ), debug
        self._record_dataset_sync("event", ticker, success=True, records_written=0, started_at=started_at)
        sync_state = self._get_sync_state("event", ticker)
        return [], self._build_data_status(
            source=None,
            updated_at=None,
            cache_hit=False,
            missing=True,
            sync_state=sync_state,
            source_metadata=self._build_source_metadata(
                None,
                attempted_sources=[item.source for item in debug],
                selection_reason="no_source_returned_data",
            ),
        ), debug

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
        partial: bool = False,
        sync_state: dict | None = None,
        source_metadata: SourceMetadata | None = None,
    ) -> DataStatus:
        if failed:
            status = "failed"
        elif missing or source is None:
            status = "missing"
        elif partial or (sync_state and sync_state.get("status") == "partial"):
            status = "partial" if not self._is_stale(updated_at) else "stale"
        elif self._is_stale(updated_at):
            status = "stale"
        else:
            status = "fresh"
        if source_metadata is None:
            source_metadata = self._build_source_metadata(source, attempted_sources=[source] if source else [])
        return DataStatus(
            status=status,
            updated_at=updated_at,
            source=source,
            ttl_hours=settings.stock_data_ttl_hours,
            cache_hit=cache_hit,
            error_message=error_message or self._sync_state_value(sync_state, "last_error_message"),
            last_synced_at=self._sync_state_value(sync_state, "last_synced_at"),
            last_success_at=self._sync_state_value(sync_state, "last_success_at"),
            last_error_at=self._sync_state_value(sync_state, "last_error_at"),
            last_error_message=self._sync_state_value(sync_state, "last_error_message"),
            source_metadata=source_metadata,
        )

    def _build_endpoint_debug(
        self,
        *,
        endpoint: str,
        data_status: DataStatus,
        sources: list[PriceSourceDebug] | None = None,
        sections: dict[str, StockSectionDebug] | None = None,
    ) -> StockEndpointDebug:
        return StockEndpointDebug(
            endpoint=endpoint,
            sources=sources or [],
            sections=sections or {},
        )

    def _build_section_debug(self, data_status: DataStatus, sources: list[PriceSourceDebug] | None = None) -> StockSectionDebug:
        return StockSectionDebug(data_status=data_status, sources=sources or [])

    def _build_data_status_sources_debug(self, data_status: DataStatus, item_count: int = 0) -> list[PriceSourceDebug]:
        source_name = data_status.source or (data_status.source_metadata.selected_source if data_status.source_metadata else None)
        if not source_name and data_status.status == "missing":
            source_name = "unavailable"
        if source_name is None:
            return []
        return [
            PriceSourceDebug(
                source=source_name,
                status=self._debug_status_from_data_status(data_status),
                count=item_count,
                kept_count=item_count,
                error=data_status.last_error_message or data_status.error_message,
            )
        ]

    def _debug_status_from_data_status(self, data_status: DataStatus) -> str:
        mapping = {
            "fresh": "ok",
            "partial": "partial",
            "stale": "stale",
            "missing": "missing",
            "failed": "error",
        }
        return mapping.get(data_status.status, data_status.status)

    def _build_overview_status(
        self,
        *,
        company_status: DataStatus,
        financial_status: DataStatus,
        price_status: DataStatus,
        event_status: DataStatus,
        risk_status: DataStatus,
    ) -> DataStatus:
        statuses = [company_status, financial_status, price_status, event_status, risk_status]
        return self._build_derived_rollup_status(statuses, selection_reason="overview_rollup")

    def _build_derived_rollup_status(
        self,
        statuses: list[DataStatus],
        *,
        selection_reason: str,
    ) -> DataStatus:
        if any(item.status == "failed" for item in statuses):
            selected = next(item for item in statuses if item.status == "failed")
            return self._build_data_status(
                source="derived",
                updated_at=selected.updated_at,
                cache_hit=True,
                error_message=selected.error_message or selected.last_error_message,
                failed=True,
                source_metadata=self._build_source_metadata("derived", attempted_sources=["derived"], returned_sources=["derived"], selection_reason=selection_reason),
            )
        if any(item.status == "stale" for item in statuses):
            selected = next(item for item in statuses if item.status == "stale")
            return self._build_data_status(
                source="derived",
                updated_at=selected.updated_at,
                cache_hit=True,
                error_message=selected.error_message or selected.last_error_message,
                partial=any(item.status == "partial" for item in statuses),
                source_metadata=self._build_source_metadata("derived", attempted_sources=["derived"], returned_sources=["derived"], selection_reason=selection_reason),
            )
        if any(item.status == "partial" for item in statuses):
            selected = next(item for item in statuses if item.status == "partial")
            return self._build_data_status(
                source="derived",
                updated_at=selected.updated_at,
                cache_hit=True,
                error_message=selected.error_message or selected.last_error_message,
                partial=True,
                source_metadata=self._build_source_metadata("derived", attempted_sources=["derived"], returned_sources=["derived"], selection_reason=selection_reason),
            )
        if all(item.status == "missing" for item in statuses):
            return self._build_data_status(
                source="derived",
                updated_at=None,
                cache_hit=True,
                missing=True,
                source_metadata=self._build_source_metadata("derived", attempted_sources=["derived"], returned_sources=["derived"], selection_reason=selection_reason),
            )
        latest_updated_at = max((item.updated_at for item in statuses if item.updated_at), default=None)
        return self._build_data_status(
            source="derived",
            updated_at=latest_updated_at,
            cache_hit=True,
            source_metadata=self._build_source_metadata("derived", attempted_sources=["derived"], returned_sources=["derived"], selection_reason=selection_reason),
        )

    def _build_risk_flags_status(
        self,
        financial_status: DataStatus,
        price_status: DataStatus,
        event_status: DataStatus,
    ) -> DataStatus:
        return self._build_derived_rollup_status(
            [financial_status, price_status, event_status],
            selection_reason="risk_flags_rollup",
        )

    def _build_signals_status(self, *, risk_status: DataStatus) -> DataStatus:
        return self._build_derived_rollup_status(
            [risk_status],
            selection_reason="signals_rollup",
        )

    def _record_dataset_sync(
        self,
        dataset: str,
        ticker: str,
        *,
        success: bool,
        started_at: datetime,
        error_message: str | None = None,
        records_written: int = 0,
    ) -> None:
        record_sync_result = getattr(self.repository, "record_sync_result", None)
        if not callable(record_sync_result):
            return
        synced_at = self._now().replace(microsecond=0).isoformat().replace("+00:00", "Z")
        duration_ms = int((self._now() - started_at).total_seconds() * 1000)
        record_sync_result(
            dataset,
            ticker,
            synced_at,
            success=success,
            error_message=error_message,
            records_written=records_written,
            duration_ms=duration_ms,
        )

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _get_sync_state(self, dataset: str, ticker: str) -> dict | None:
        get_sync_state = getattr(self.repository, "get_sync_state", None)
        if callable(get_sync_state):
            return get_sync_state(dataset, ticker)
        last_synced_at = self.repository.get_last_synced_at(dataset, ticker)
        if not last_synced_at:
            return None
        return {
            "last_synced_at": last_synced_at,
            "last_success_at": last_synced_at,
            "last_error_at": None,
            "last_error_message": None,
        }

    def _sync_state_value(self, sync_state: dict | None, key: str) -> str | None:
        if not sync_state:
            return None
        value = sync_state.get(key)
        return str(value) if value is not None else None

    def _build_source_metadata(
        self,
        selected_source: str | None,
        *,
        attempted_sources: list[str] | None = None,
        returned_sources: list[str] | None = None,
        fallback_used: bool = False,
        selection_reason: str | None = None,
        fallback_reason: str | None = None,
    ) -> SourceMetadata:
        sources = []
        for source_name in attempted_sources or []:
            if source_name and source_name not in sources:
                sources.append(source_name)
        kept_sources = []
        for source_name in returned_sources or []:
            if source_name and source_name not in kept_sources:
                kept_sources.append(source_name)
        return SourceMetadata(
            selected_source=selected_source,
            selected_source_priority=get_source_priority(selected_source) if selected_source else None,
            fallback_used=fallback_used,
            attempted_sources=sources,
            returned_sources=kept_sources,
            selection_reason=selection_reason,
            fallback_reason=fallback_reason,
        )

    def _build_fallback_reason(
        self,
        *,
        selected_source: str | None,
        attempted_sources: list[str],
        returned_sources: list[str],
        error_message: str | None = None,
    ) -> str | None:
        if error_message:
            return error_message
        if selected_source and attempted_sources and selected_source != attempted_sources[0]:
            return f"Selected {selected_source} because it outranked earlier source attempts."
        if len(returned_sources) > 1:
            return "Returned rows from multiple sources after source-priority evaluation."
        return None

    def _select_runtime_source(self, available_sources: list[str]) -> str | None:
        candidates = [source_name for source_name in available_sources if source_name]
        if not candidates:
            return None
        return sorted(
            candidates,
            key=lambda source_name: (get_source_priority(source_name), source_name),
            reverse=True,
        )[0]

    def _event_sources(self, events: list[Event]) -> list[str]:
        sources: list[str] = []
        for event in events:
            if event.source and event.source not in sources:
                sources.append(event.source)
        return sources

    def _select_primary_event_source(self, events: list[Event]) -> str | None:
        counts: dict[str, int] = {}
        for event in events:
            counts[event.source] = counts.get(event.source, 0) + 1
        if not counts:
            return None
        return sorted(
            counts,
            key=lambda source_name: (get_source_priority(source_name), counts[source_name], source_name),
            reverse=True,
        )[0]

    def _event_importance_rank(self, event: Event) -> int:
        importance_rank = {"high": 3, "medium": 2, "low": 1}
        return importance_rank.get(event.importance, 0)

    def _sort_events_for_output(self, events: list[Event]) -> list[Event]:
        ordered = sorted(events, key=lambda item: item.dedupe_key or item.event_id or "")
        ordered = sorted(ordered, key=lambda item: item.title or "")
        ordered = sorted(ordered, key=lambda item: item.updated_at or "", reverse=True)
        ordered = sorted(ordered, key=lambda item: item.source_priority or 0, reverse=True)
        ordered = sorted(ordered, key=lambda item: self._event_importance_rank(item), reverse=True)
        ordered = sorted(ordered, key=lambda item: item.event_date or "", reverse=True)
        return ordered

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
                continue
            if (
                event.source_priority == existing.source_priority
                and (event.updated_at or "") == (existing.updated_at or "")
                and (event.event_id or "") < (existing.event_id or "")
            ):
                deduped[key] = event
        return self._sort_events_for_output(list(deduped.values()))[:limit]

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
