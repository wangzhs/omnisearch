from datetime import datetime, timedelta, timezone

from app.collectors.akshare import AKShareCollector
from app.collectors.cninfo import CNInfoCollector
from app.collectors.exchange_search import ExchangeSearchCollector
from app.collectors.tushare import TushareCollector
from app.core.config import settings
from app.db.sqlite import get_repository
from app.models.stock import CompanyProfile, Event, FinancialSummary, PriceDaily
from app.normalizers.stock import (
    normalize_cninfo_event,
    normalize_company_profile,
    normalize_financial_summary,
    normalize_price_daily,
    normalize_ticker_input,
)
from app.schemas.stock import (
    CompanyOverview,
    EventListDebugResponse,
    EventSourceDebug,
    PriceListDebugResponse,
    PriceSourceDebug,
    RiskFlag,
    StockResearchContext,
    TimelineItem,
)


class StockDataService:
    def __init__(
        self,
        repository=None,
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
        normalized = normalize_ticker_input(ticker)
        profile = self.repository.get_company_profile(normalized)
        if profile and not self._should_refresh("company_profile", normalized, refresh):
            return profile

        raw = self.tushare_collector.fetch_company_profile(normalized)
        if not raw:
            if profile:
                return profile
            raise RuntimeError(f"No company profile found for {normalized}")

        normalized_profile = normalize_company_profile(normalized, raw)
        return self.repository.upsert_company_profile(normalized_profile)

    def list_events(self, ticker: str, limit: int = 20, refresh: bool = False) -> list[Event]:
        return self.list_events_with_debug(ticker=ticker, limit=limit, refresh=refresh).items

    def list_events_with_debug(self, ticker: str, limit: int = 20, refresh: bool = False) -> EventListDebugResponse:
        normalized = normalize_ticker_input(ticker)
        cached = self.repository.list_events(normalized, limit=limit)
        if cached and not self._should_refresh("event", normalized, refresh):
            return EventListDebugResponse(
                ticker=normalized,
                items=cached,
                debug=[EventSourceDebug(source="cache", status="hit", count=len(cached), kept_count=len(cached))],
            )

        debug: list[EventSourceDebug] = []
        raw_events: list[dict] = []
        try:
            raw_events = self.cninfo_collector.fetch_events(normalized, limit=limit)
            debug.append(
                EventSourceDebug(
                    source="cninfo",
                    status="ok" if raw_events else "empty",
                    count=len(raw_events),
                    kept_count=len(raw_events),
                )
            )
        except RuntimeError:
            debug.append(EventSourceDebug(source="cninfo", status="error", error="fetch_failed"))
            raw_events = []

        events = [normalize_cninfo_event(normalized, raw) for raw in raw_events]

        if not events:
            company_name = None
            try:
                company_name = self.get_company(normalized, refresh=refresh).name
            except RuntimeError:
                company_name = None
            fallback_payload = self.exchange_search_collector.fetch_events_with_debug(
                normalized,
                company_name=company_name,
                limit=limit,
            )
            fallback_raw_events = fallback_payload["items"]
            debug.append(EventSourceDebug(**fallback_payload["debug"]))
            events = [Event(**item) for item in fallback_raw_events]

        if events:
            if refresh:
                self.repository.replace_events(normalized, events)
            else:
                self.repository.upsert_events(normalized, events)
        latest = self.repository.list_events(normalized, limit=limit)
        return EventListDebugResponse(
            ticker=normalized,
            items=latest,
            debug=debug,
        )

    def list_financials(self, ticker: str, limit: int = 8, refresh: bool = False) -> list[FinancialSummary]:
        normalized = normalize_ticker_input(ticker)
        cached = self.repository.list_financial_summaries(normalized, limit=limit)
        if cached and not self._should_refresh("financial_summary", normalized, refresh):
            return cached

        raw_items = self.tushare_collector.fetch_financial_summaries(normalized, limit=limit)
        items = [normalize_financial_summary(normalized, raw) for raw in raw_items]
        if items:
            self.repository.upsert_financial_summaries(normalized, items)
        return self.repository.list_financial_summaries(normalized, limit=limit)

    def list_prices(
        self,
        ticker: str,
        limit: int = 60,
        start_date: str | None = None,
        end_date: str | None = None,
        refresh: bool = False,
    ) -> list[PriceDaily]:
        normalized = normalize_ticker_input(ticker)
        cached = self.repository.list_prices(normalized, limit=limit, start_date=start_date, end_date=end_date)
        if cached and not self._should_refresh("price_daily", normalized, refresh):
            return list(reversed(cached))

        try:
            raw_prices = self.akshare_collector.fetch_daily_prices(
                normalized,
                limit=limit,
                start_date=start_date,
                end_date=end_date,
            )
        except RuntimeError:
            raw_prices = self.tushare_collector.fetch_daily_prices(
                normalized,
                limit=limit,
                start_date=start_date,
                end_date=end_date,
            )
        prices = [normalize_price_daily(normalized, raw) for raw in raw_prices]
        if prices:
            self.repository.upsert_prices(normalized, prices)
        latest = self.repository.list_prices(normalized, limit=limit, start_date=start_date, end_date=end_date)
        return list(reversed(latest))

    def list_prices_with_debug(
        self,
        ticker: str,
        limit: int = 60,
        start_date: str | None = None,
        end_date: str | None = None,
        refresh: bool = False,
    ) -> PriceListDebugResponse:
        normalized = normalize_ticker_input(ticker)
        cached = self.repository.list_prices(normalized, limit=limit, start_date=start_date, end_date=end_date)
        if cached and not self._should_refresh("price_daily", normalized, refresh):
            return PriceListDebugResponse(
                ticker=normalized,
                items=list(reversed(cached)),
                debug=[PriceSourceDebug(source="cache", status="hit", count=len(cached))],
            )

        debug: list[PriceSourceDebug] = []
        raw_prices: list[dict] = []

        try:
            raw_prices = self.akshare_collector.fetch_daily_prices(
                normalized,
                limit=limit,
                start_date=start_date,
                end_date=end_date,
            )
            debug.append(
                PriceSourceDebug(
                    source="akshare",
                    status="ok" if raw_prices else "empty",
                    count=len(raw_prices),
                )
            )
        except RuntimeError as exc:
            debug.append(PriceSourceDebug(source="akshare", status="error", error=str(exc)))

        if not raw_prices:
            try:
                raw_prices = self.tushare_collector.fetch_daily_prices(
                    normalized,
                    limit=limit,
                    start_date=start_date,
                    end_date=end_date,
                )
                debug.append(
                    PriceSourceDebug(
                        source="tushare",
                        status="ok" if raw_prices else "empty",
                        count=len(raw_prices),
                    )
                )
            except RuntimeError as exc:
                debug.append(PriceSourceDebug(source="tushare", status="error", error=str(exc)))
                raise RuntimeError(
                    "; ".join(
                        f"{item.source}:{item.status}" + (f": {item.error}" if item.error else "")
                        for item in debug
                    )
                ) from exc

        prices = [normalize_price_daily(normalized, raw) for raw in raw_prices]
        if prices:
            self.repository.upsert_prices(normalized, prices)
        latest = self.repository.list_prices(normalized, limit=limit, start_date=start_date, end_date=end_date)
        return PriceListDebugResponse(
            ticker=normalized,
            items=list(reversed(latest)),
            debug=debug,
        )

    def get_overview(self, ticker: str, refresh: bool = False) -> CompanyOverview:
        normalized = normalize_ticker_input(ticker)
        try:
            company = self.get_company(normalized, refresh=refresh)
        except RuntimeError:
            company = self._build_placeholder_company(normalized)
        events = self.list_events(ticker, limit=5, refresh=refresh)
        financials = self.list_financials(ticker, limit=4, refresh=refresh)
        prices = self.list_prices(ticker, limit=30, refresh=refresh)
        latest_financial = financials[0] if financials else None
        latest_price = prices[-1] if prices else None
        risk_flags = self.get_risk_flags(ticker, refresh=refresh)
        return CompanyOverview(
            company=company,
            latest_financial=latest_financial,
            latest_price=latest_price,
            recent_events=events,
            risk_flags=risk_flags,
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
                    importance=event.importance or ("high" if event.category else "medium"),
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
            ticker=overview.company.ticker,
            company=overview.company,
            recent_events=overview.recent_events,
            latest_financial=overview.latest_financial,
            latest_price=overview.latest_price,
            risk_flags=overview.risk_flags,
        )

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
            status="unknown",
            raw={},
        )


_stock_data_service: StockDataService | None = None


def get_stock_data_service() -> StockDataService:
    global _stock_data_service
    if _stock_data_service is None:
        _stock_data_service = StockDataService()
    return _stock_data_service
