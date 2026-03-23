from app.models.stock import CompanyProfile, Event
from app.models.stock import FinancialSummary, PriceDaily
from app.normalizers.stock import build_event_dedupe_key
from app.services.stock import StockDataService


def test_build_data_status_returns_fresh_for_recent_data() -> None:
    service = StockDataService(repository=type("Repo", (), {})())

    status = service._build_data_status(
        source="tushare",
        updated_at="2099-01-01T00:00:00Z",
        cache_hit=False,
    )

    assert status.status == "fresh"
    assert status.cache_hit is False
    assert status.source == "tushare"
    assert status.source_metadata.selected_source == "tushare"


def test_build_data_status_returns_stale_for_expired_cache() -> None:
    service = StockDataService(repository=type("Repo", (), {})())

    status = service._build_data_status(
        source="tushare",
        updated_at="2000-01-01T00:00:00Z",
        cache_hit=True,
    )

    assert status.status == "stale"
    assert status.cache_hit is True
    assert status.source == "tushare"


def test_build_data_status_returns_failed_when_fetch_failed() -> None:
    service = StockDataService(repository=type("Repo", (), {})())

    status = service._build_data_status(
        source="cninfo",
        updated_at=None,
        cache_hit=False,
        error_message="timeout",
        failed=True,
    )

    assert status.status == "failed"
    assert status.error_message == "timeout"


def test_build_data_status_marks_fallback_source_usage() -> None:
    service = StockDataService(repository=type("Repo", (), {})())

    status = service._build_data_status(
        source="tushare",
        updated_at="2099-01-01T00:00:00Z",
        cache_hit=False,
        source_metadata=service._build_source_metadata(
            "tushare",
            attempted_sources=["akshare", "tushare"],
            fallback_used=True,
        ),
    )

    assert status.source_metadata.fallback_used is True
    assert status.source_metadata.attempted_sources == ["akshare", "tushare"]


def test_build_data_status_returns_partial_when_cached_data_has_upstream_error() -> None:
    service = StockDataService(repository=type("Repo", (), {})())

    status = service._build_data_status(
        source="tushare",
        updated_at="2099-01-01T00:00:00Z",
        cache_hit=True,
        error_message="retry pending",
        partial=True,
    )

    assert status.status == "partial"
    assert status.error_message == "retry pending"


def test_build_data_status_returns_missing_when_source_absent() -> None:
    service = StockDataService(repository=type("Repo", (), {})())

    status = service._build_data_status(
        source=None,
        updated_at=None,
        cache_hit=False,
        missing=True,
    )

    assert status.status == "missing"
    assert status.source is None


def test_risk_flag_status_rolls_up_failed_and_stale_inputs() -> None:
    service = StockDataService(repository=type("Repo", (), {})())

    risk_status = service._build_risk_flags_status(
        financial_status=service._build_data_status(source="tushare", updated_at="2000-01-01T00:00:00Z", cache_hit=True),
        price_status=service._build_data_status(source="akshare", updated_at=None, cache_hit=False, failed=True, error_message="down"),
        event_status=service._build_data_status(source=None, updated_at=None, cache_hit=False, missing=True),
    )

    assert risk_status.status == "failed"
    assert risk_status.source == "derived"


def test_overview_status_rolls_up_partial_when_any_section_is_partial() -> None:
    service = StockDataService(repository=type("Repo", (), {})())

    overview_status = service._build_overview_status(
        company_status=service._build_data_status(source="tushare", updated_at="2099-01-01T00:00:00Z", cache_hit=True),
        financial_status=service._build_data_status(
            source="tushare",
            updated_at="2099-01-01T00:00:00Z",
            cache_hit=True,
            partial=True,
            error_message="financial retry pending",
        ),
        price_status=service._build_data_status(source="akshare", updated_at="2099-01-01T00:00:00Z", cache_hit=True),
        event_status=service._build_data_status(source="cninfo", updated_at="2099-01-01T00:00:00Z", cache_hit=True),
        risk_status=service._build_data_status(source="derived", updated_at="2099-01-01T00:00:00Z", cache_hit=True),
    )

    assert overview_status.status == "partial"
    assert overview_status.source == "derived"
    assert overview_status.error_message == "financial retry pending"


def test_overview_status_rolls_up_stale_when_any_section_is_stale_and_none_failed() -> None:
    service = StockDataService(repository=type("Repo", (), {})())

    overview_status = service._build_overview_status(
        company_status=service._build_data_status(source="tushare", updated_at="2099-01-01T00:00:00Z", cache_hit=True),
        financial_status=service._build_data_status(source="tushare", updated_at="2000-01-01T00:00:00Z", cache_hit=True),
        price_status=service._build_data_status(source="akshare", updated_at="2099-01-01T00:00:00Z", cache_hit=True),
        event_status=service._build_data_status(source="cninfo", updated_at="2099-01-01T00:00:00Z", cache_hit=True),
        risk_status=service._build_data_status(source="derived", updated_at="2099-01-01T00:00:00Z", cache_hit=True),
    )

    assert overview_status.status == "stale"
    assert overview_status.source == "derived"


def test_overview_status_rolls_up_failed_when_critical_section_fails() -> None:
    service = StockDataService(repository=type("Repo", (), {})())

    overview_status = service._build_overview_status(
        company_status=service._build_data_status(source="tushare", updated_at="2099-01-01T00:00:00Z", cache_hit=True),
        financial_status=service._build_data_status(source="tushare", updated_at="2099-01-01T00:00:00Z", cache_hit=True),
        price_status=service._build_data_status(
            source="akshare",
            updated_at=None,
            cache_hit=False,
            failed=True,
            error_message="price upstream down",
        ),
        event_status=service._build_data_status(source="cninfo", updated_at="2099-01-01T00:00:00Z", cache_hit=True),
        risk_status=service._build_data_status(source="derived", updated_at="2099-01-01T00:00:00Z", cache_hit=True),
    )

    assert overview_status.status == "failed"
    assert overview_status.source == "derived"
    assert overview_status.error_message == "price upstream down"


def test_event_dedupe_prefers_higher_priority_source() -> None:
    service = StockDataService(repository=type("Repo", (), {})())
    low_priority = Event(
        event_id="evt-low",
        dedupe_key="same-key",
        ticker="000001.SZ",
        event_date="2026-03-16",
        title="同一事件",
        raw_title="同一事件",
        event_type="general_disclosure",
        sentiment="neutral",
        source_type="exchange_search",
        source="exchange_search",
        source_priority=60,
        importance="low",
    )
    high_priority = Event(
        event_id="evt-high",
        dedupe_key="same-key",
        ticker="000001.SZ",
        event_date="2026-03-16",
        title="同一事件",
        raw_title="同一事件",
        event_type="regulatory_action",
        sentiment="negative",
        source_type="filing",
        source="cninfo",
        source_priority=100,
        importance="high",
    )

    deduped = service._dedupe_events([low_priority, high_priority], limit=10)

    assert len(deduped) == 1
    assert deduped[0].source == "cninfo"
    assert deduped[0].event_type == "regulatory_action"


def test_event_dedupe_collapses_cross_source_same_day_title_variants() -> None:
    service = StockDataService(repository=type("Repo", (), {})())
    cninfo_event = Event(
        event_id="cninfo-1",
        dedupe_key=build_event_dedupe_key("000001.SZ", "关于 2026 年报的公告", "2026-03-16", "https://static.cninfo.com.cn/a.pdf"),
        ticker="000001.SZ",
        event_date="2026-03-16",
        title="关于 2026 年报的公告",
        raw_title="关于 2026 年报的公告",
        event_type="financial_report",
        sentiment="neutral",
        source_type="filing",
        source="cninfo",
        source_priority=100,
        importance="high",
    )
    exchange_event = Event(
        event_id="search-1",
        dedupe_key=build_event_dedupe_key("000001.SZ", "关于2026年报的公告", "2026-03-16", "https://www.szse.cn/disclosure/b"),
        ticker="000001.SZ",
        event_date="2026-03-16",
        title="关于2026年报的公告",
        raw_title="关于2026年报的公告",
        event_type="financial_report",
        sentiment="neutral",
        source_type="exchange_search",
        source="exchange_search",
        source_priority=60,
        importance="high",
    )

    deduped = service._dedupe_events([exchange_event, cninfo_event], limit=10)

    assert len(deduped) == 1
    assert deduped[0].source == "cninfo"
    assert deduped[0].title == "关于 2026 年报的公告"


def test_event_dedupe_collapses_prefix_noise_and_keeps_higher_priority_source() -> None:
    service = StockDataService(repository=type("Repo", (), {})())
    exchange_event = Event(
        event_id="search-1",
        dedupe_key=build_event_dedupe_key("000001.SZ", "【公告】关于2026年报的公告", "2026-03-16", "https://www.szse.cn/disclosure/a"),
        ticker="000001.SZ",
        event_date="2026-03-16",
        title="【公告】关于2026年报的公告",
        raw_title="【公告】关于2026年报的公告",
        event_type="financial_report",
        sentiment="neutral",
        source_type="exchange_search",
        source="exchange_search",
        source_priority=60,
        importance="high",
    )
    cninfo_event = Event(
        event_id="cninfo-1",
        dedupe_key=build_event_dedupe_key("000001.SZ", "关于2026年报的公告", "2026-03-16", "https://static.cninfo.com.cn/a.pdf"),
        ticker="000001.SZ",
        event_date="2026-03-16",
        title="关于2026年报的公告",
        raw_title="关于2026年报的公告",
        event_type="financial_report",
        sentiment="neutral",
        source_type="filing",
        source="cninfo",
        source_priority=100,
        importance="high",
    )

    deduped = service._dedupe_events([exchange_event, cninfo_event], limit=10)

    assert len(deduped) == 1
    assert deduped[0].source == "cninfo"
    assert deduped[0].dedupe_key == cninfo_event.dedupe_key


def test_event_dedupe_sorts_same_date_items_deterministically() -> None:
    service = StockDataService(repository=type("Repo", (), {})())
    events = [
        Event(
            event_id="evt-b",
            dedupe_key="dedupe-b",
            ticker="000001.SZ",
            event_date="2026-03-16",
            title="B公告",
            raw_title="B公告",
            event_type="general_disclosure",
            sentiment="neutral",
            source_type="filing",
            source="cninfo",
            source_priority=100,
            importance="medium",
            updated_at="2026-03-16T09:00:00Z",
        ),
        Event(
            event_id="evt-a",
            dedupe_key="dedupe-a",
            ticker="000001.SZ",
            event_date="2026-03-16",
            title="A公告",
            raw_title="A公告",
            event_type="general_disclosure",
            sentiment="neutral",
            source_type="filing",
            source="cninfo",
            source_priority=100,
            importance="medium",
            updated_at="2026-03-16T09:00:00Z",
        ),
        Event(
            event_id="evt-z",
            dedupe_key="dedupe-z",
            ticker="000001.SZ",
            event_date="2026-03-16",
            title="Z公告",
            raw_title="Z公告",
            event_type="general_disclosure",
            sentiment="neutral",
            source_type="filing",
            source="cninfo",
            source_priority=100,
            importance="high",
            updated_at="2026-03-16T09:00:00Z",
        ),
    ]

    ordered = service._dedupe_events(events, limit=10)

    assert [item.event_id for item in ordered] == ["evt-z", "evt-a", "evt-b"]


def test_event_dedupe_collapses_same_source_records_with_empty_titles_by_url() -> None:
    service = StockDataService(repository=type("Repo", (), {})())
    first = Event(
        event_id="evt-b",
        dedupe_key=build_event_dedupe_key("000001.SZ", "", "2026-03-16", "https://example.com/a.pdf"),
        ticker="000001.SZ",
        event_date="2026-03-16",
        title="",
        raw_title="",
        event_type="general_disclosure",
        sentiment="neutral",
        source_type="filing",
        source="cninfo",
        source_priority=100,
        url="https://example.com/a.pdf",
        source_url="https://example.com/a.pdf",
        importance="medium",
        updated_at="2026-03-16T09:00:00Z",
    )
    second = Event(
        event_id="evt-a",
        dedupe_key=build_event_dedupe_key("000001.SZ", "【】", "2026-03-16", "https://example.com/a.pdf"),
        ticker="000001.SZ",
        event_date="2026-03-16",
        title="【】",
        raw_title="【】",
        event_type="general_disclosure",
        sentiment="neutral",
        source_type="filing",
        source="cninfo",
        source_priority=100,
        url="https://example.com/a.pdf",
        source_url="https://example.com/a.pdf",
        importance="medium",
        updated_at="2026-03-16T09:00:00Z",
    )

    deduped = service._dedupe_events([first, second], limit=10)

    assert len(deduped) == 1
    assert deduped[0].event_id == "evt-a"


def test_event_dedupe_does_not_over_merge_cross_source_url_only_records() -> None:
    service = StockDataService(repository=type("Repo", (), {})())
    first = Event(
        event_id="evt-1",
        dedupe_key=build_event_dedupe_key("000001.SZ", "", None, "https://example.com/a.pdf"),
        ticker="000001.SZ",
        event_date=None,
        title="",
        raw_title="",
        event_type="general_disclosure",
        sentiment="neutral",
        source_type="filing",
        source="cninfo",
        source_priority=100,
        url="https://example.com/a.pdf",
        source_url="https://example.com/a.pdf",
        importance="medium",
        updated_at="2026-03-16T09:00:00Z",
    )
    second = Event(
        event_id="evt-2",
        dedupe_key=build_event_dedupe_key("000001.SZ", "", None, "https://example.com/b.pdf"),
        ticker="000001.SZ",
        event_date=None,
        title="",
        raw_title="",
        event_type="general_disclosure",
        sentiment="neutral",
        source_type="exchange_search",
        source="exchange_search",
        source_priority=60,
        url="https://example.com/b.pdf",
        source_url="https://example.com/b.pdf",
        importance="medium",
        updated_at="2026-03-16T09:00:00Z",
    )

    deduped = service._dedupe_events([first, second], limit=10)

    assert len(deduped) == 2
    assert [item.event_id for item in deduped] == ["evt-1", "evt-2"]


def test_event_dedupe_with_missing_date_remains_stable_for_identical_url_fallback_records() -> None:
    service = StockDataService(repository=type("Repo", (), {})())
    higher_priority = Event(
        event_id="evt-high",
        dedupe_key=build_event_dedupe_key("000001.SZ", "", None, "https://example.com/a.pdf"),
        ticker="000001.SZ",
        event_date=None,
        title="",
        raw_title="",
        event_type="general_disclosure",
        sentiment="neutral",
        source_type="filing",
        source="cninfo",
        source_priority=100,
        url="https://example.com/a.pdf",
        source_url="https://example.com/a.pdf",
        importance="medium",
        updated_at="2026-03-16T09:00:00Z",
    )
    lower_priority = Event(
        event_id="evt-low",
        dedupe_key=build_event_dedupe_key("000001.SZ", "【】", None, "https://example.com/a.pdf"),
        ticker="000001.SZ",
        event_date=None,
        title="【】",
        raw_title="【】",
        event_type="general_disclosure",
        sentiment="neutral",
        source_type="exchange_search",
        source="exchange_search",
        source_priority=60,
        url="https://example.com/a.pdf",
        source_url="https://example.com/a.pdf",
        importance="medium",
        updated_at="2026-03-16T09:00:00Z",
    )

    deduped = service._dedupe_events([lower_priority, higher_priority], limit=10)

    assert len(deduped) == 1
    assert deduped[0].event_id == "evt-high"


def test_build_overview_signals_returns_agent_ready_summary() -> None:
    service = StockDataService(repository=type("Repo", (), {})())

    signals = service._build_overview_signals(
        latest_financial=FinancialSummary(
            record_id="000001.SZ:2025-12-31:annual",
            dedupe_key="000001.SZ:2025-12-31:annual",
            ticker="000001.SZ",
            report_date="2025-12-31",
            net_profit=-1.0,
            source="tushare",
        ),
        latest_price=PriceDaily(
            ticker="000001.SZ",
            trade_date="2026-03-17",
            dedupe_key="000001.SZ:2026-03-17",
            close=10.8,
            change_pct=8.5,
            source="akshare",
        ),
        recent_events=[
            Event(
                event_id="evt-1",
                dedupe_key="evt-1",
                ticker="000001.SZ",
                event_date="2026-03-16",
                title="Annual report disclosed",
                raw_title="Annual report disclosed",
                event_type="financial_report",
                sentiment="neutral",
                source_type="filing",
                source="cninfo",
                importance="high",
            )
        ],
        risk_flags=[],
    )

    codes = {item.code for item in signals}
    assert "profitability" in codes
    assert "latest_price_move" in codes
    assert "disclosure_activity" in codes


def test_timeline_sorts_latest_items_first() -> None:
    class FakeService(StockDataService):
        def list_events(self, ticker: str, limit: int = 20, refresh: bool = False):
            return [
                Event(
                    event_id="evt-1",
                    dedupe_key="evt-1",
                    ticker="000001.SZ",
                    event_date="2026-03-16",
                    title="Annual report disclosed",
                    raw_title="Annual report disclosed",
                    event_type="financial_report",
                    sentiment="neutral",
                    source_type="filing",
                    source="cninfo",
                    importance="high",
                )
            ]

        def list_financials(self, ticker: str, limit: int = 8, refresh: bool = False):
            return [
                FinancialSummary(
                    record_id="000001.SZ:2025-12-31:annual",
                    dedupe_key="000001.SZ:2025-12-31:annual",
                    ticker="000001.SZ",
                    report_date="2025-12-31",
                    announcement_date="2026-03-17",
                    net_profit=1.0,
                    source="tushare",
                )
            ]

        def list_prices(self, ticker: str, limit: int = 60, start_date=None, end_date=None, refresh: bool = False):
            return [
                PriceDaily(
                    ticker="000001.SZ",
                    trade_date="2026-03-18",
                    dedupe_key="000001.SZ:2026-03-18",
                    close=10.5,
                    change_pct=5.0,
                    source="akshare",
                )
            ]

    timeline = FakeService(repository=type("Repo", (), {})()).get_timeline("000001")

    assert timeline[0].date == "2026-03-18"
    assert timeline[0].kind == "price"


def test_risk_flags_capture_drawdown_and_volatility() -> None:
    class FakeService(StockDataService):
        def list_financials(self, ticker: str, limit: int = 4, refresh: bool = False):
            return []

        def list_prices(self, ticker: str, limit: int = 30, start_date=None, end_date=None, refresh: bool = False):
            return [
                PriceDaily(ticker="000001.SZ", trade_date="2026-03-10", dedupe_key="1", close=12.0, change_pct=1.0, source="akshare"),
                PriceDaily(ticker="000001.SZ", trade_date="2026-03-11", dedupe_key="2", close=11.0, change_pct=9.2, source="akshare"),
                PriceDaily(ticker="000001.SZ", trade_date="2026-03-12", dedupe_key="3", close=10.0, change_pct=-8.5, source="akshare"),
                PriceDaily(ticker="000001.SZ", trade_date="2026-03-13", dedupe_key="4", close=10.2, change_pct=2.1, source="akshare"),
                PriceDaily(ticker="000001.SZ", trade_date="2026-03-14", dedupe_key="5", close=10.1, change_pct=-1.0, source="akshare"),
            ]

        def list_events(self, ticker: str, limit: int = 10, refresh: bool = False):
            return []

    flags = FakeService(repository=type("Repo", (), {})()).get_risk_flags("000001")
    codes = {flag.code for flag in flags}

    assert "price_volatility" in codes
    assert "recent_drawdown" in codes


def test_overview_does_not_reload_sections_for_risk_flags() -> None:
    class CountingService(StockDataService):
        def __init__(self):
            super().__init__(repository=type("Repo", (), {})())
            self.calls = {"company": 0, "financials": 0, "prices": 0, "events": 0, "overview_status": 0}

        def _load_company(self, ticker: str, refresh: bool = False):
            self.calls["company"] += 1
            return (
                CompanyProfile(ticker=ticker, dedupe_key=ticker, source="tushare", source_priority=100),
                self._build_data_status(source="tushare", updated_at="2099-01-01T00:00:00Z", cache_hit=True),
            )

        def _load_financials(self, ticker: str, limit: int = 8, refresh: bool = False):
            self.calls["financials"] += 1
            return (
                [FinancialSummary(record_id=f"{ticker}:2025-12-31:annual", dedupe_key=f"{ticker}:2025-12-31:annual", ticker=ticker, report_date="2025-12-31", net_profit=-1.0, source="tushare")],
                self._build_data_status(source="tushare", updated_at="2099-01-01T00:00:00Z", cache_hit=True),
            )

        def _load_prices(self, ticker: str, limit: int = 60, start_date=None, end_date=None, refresh: bool = False):
            self.calls["prices"] += 1
            return (
                [PriceDaily(ticker=ticker, trade_date="2026-03-17", dedupe_key=f"{ticker}:2026-03-17", close=10.0, change_pct=5.0, source="akshare")],
                self._build_data_status(source="akshare", updated_at="2099-01-01T00:00:00Z", cache_hit=True),
                [],
            )

        def _load_events(self, ticker: str, limit: int = 20, refresh: bool = False):
            self.calls["events"] += 1
            return (
                [Event(event_id="evt-1", dedupe_key="evt-1", ticker=ticker, event_date="2026-03-16", title="风险提示公告", raw_title="风险提示公告", event_type="general_disclosure", sentiment="negative", source_type="filing", source="cninfo", importance="high")],
                self._build_data_status(source="cninfo", updated_at="2099-01-01T00:00:00Z", cache_hit=True),
                [],
            )

        def _build_overview_status(self, **kwargs):
            self.calls["overview_status"] += 1
            return super()._build_overview_status(**kwargs)

    service = CountingService()

    payload = service.get_overview_with_debug("000001.SZ")

    assert payload.data.risk_flags.data
    assert payload.debug.sections["risk_flags"].data_status.status == "fresh"
    assert service.calls["company"] == 1
    assert service.calls["financials"] == 1
    assert service.calls["prices"] == 1
    assert service.calls["events"] == 1
    assert service.calls["overview_status"] == 1


def test_overview_debug_preserves_section_structure_and_rollup_status() -> None:
    class PartialOverviewService(StockDataService):
        def _load_company(self, ticker: str, refresh: bool = False):
            return (
                CompanyProfile(ticker=ticker, dedupe_key=ticker, source="tushare", source_priority=100),
                self._build_data_status(source="tushare", updated_at="2099-01-01T00:00:00Z", cache_hit=True),
            )

        def _load_financials(self, ticker: str, limit: int = 8, refresh: bool = False):
            return (
                [],
                self._build_data_status(source="tushare", updated_at="2099-01-01T00:00:00Z", cache_hit=True, partial=True, error_message="partial"),
            )

        def _load_prices(self, ticker: str, limit: int = 60, start_date=None, end_date=None, refresh: bool = False):
            return (
                [],
                self._build_data_status(source="akshare", updated_at="2099-01-01T00:00:00Z", cache_hit=True),
                [],
            )

        def _load_events(self, ticker: str, limit: int = 20, refresh: bool = False):
            return (
                [],
                self._build_data_status(source="cninfo", updated_at="2099-01-01T00:00:00Z", cache_hit=True),
                [],
            )

    payload = PartialOverviewService(repository=type("Repo", (), {})()).get_overview_with_debug("000001.SZ")

    assert payload.debug.endpoint == "company_overview"
    assert set(payload.debug.sections) == {"company", "latest_financial", "latest_price", "recent_events", "risk_flags", "signals"}
    assert payload.data_status.status == "partial"
    assert payload.debug.sections["latest_financial"].data_status.status == "partial"


def test_risk_flag_status_propagates_partial_inputs() -> None:
    service = StockDataService(repository=type("Repo", (), {})())

    risk_status = service._build_risk_flags_status(
        financial_status=service._build_data_status(source="tushare", updated_at="2099-01-01T00:00:00Z", cache_hit=True, partial=True, error_message="partial upstream"),
        price_status=service._build_data_status(source="akshare", updated_at="2099-01-01T00:00:00Z", cache_hit=True),
        event_status=service._build_data_status(source="cninfo", updated_at="2099-01-01T00:00:00Z", cache_hit=True),
    )

    assert risk_status.status == "partial"


def test_runtime_sync_recording_covers_all_primary_datasets() -> None:
    recorded = []

    class FakeRepository:
        def __init__(self):
            self.prices = []
            self.events = []
            self.financials = []

        def get_company_profile(self, ticker: str):
            return None

        def upsert_company_profile(self, profile):
            return profile

        def list_financial_summaries(self, ticker: str, limit: int = 8):
            return self.financials

        def upsert_financial_summaries(self, ticker: str, items):
            self.financials = items
            return items

        def list_prices(self, ticker: str, limit: int = 60, start_date=None, end_date=None):
            return self.prices

        def upsert_prices(self, ticker: str, prices):
            self.prices = prices
            return prices

        def list_events(self, ticker: str, limit: int = 20):
            return self.events

        def upsert_events(self, ticker: str, events):
            self.events = events
            return events

        def replace_events(self, ticker: str, events):
            self.events = events
            return events

        def get_last_synced_at(self, dataset: str, ticker: str):
            return None

        def get_sync_state(self, dataset: str, ticker: str):
            return None

        def record_sync_result(self, dataset: str, ticker: str, synced_at: str, **kwargs):
            recorded.append({"dataset": dataset, "ticker": ticker, "synced_at": synced_at, **kwargs})

    class FakeTushareCollector:
        def fetch_company_profile(self, ticker: str):
            return {"basic": {"name": "平安银行", "market": "主板", "industry": "银行", "list_status": "L"}, "company": {}}

        def fetch_financial_summaries(self, ticker: str, limit: int = 8):
            return [{"end_date": "20251231", "report_type": "annual", "n_income": 1.0}]

        def fetch_daily_prices(self, ticker: str, limit: int = 60, start_date=None, end_date=None):
            return [{"trade_date": "20260317", "close": 10.5, "source": "tushare"}]

    class FakeCNInfoCollector:
        def fetch_events(self, ticker: str, limit: int = 20):
            return [{"announcementTitle": "关于年报的公告", "announcementTime": "2026-03-16", "adjunctUrl": "finalpage/test.pdf"}]

    class FakeAKShareCollector:
        def fetch_daily_prices(self, ticker: str, limit: int = 60, start_date=None, end_date=None):
            return [{"trade_date": "20260317", "close": 10.5, "source": "akshare"}]

    service = StockDataService(
        repository=FakeRepository(),
        tushare_collector=FakeTushareCollector(),
        cninfo_collector=FakeCNInfoCollector(),
        akshare_collector=FakeAKShareCollector(),
    )

    service._load_company("000001.SZ")
    service._load_financials("000001.SZ")
    service._load_prices("000001.SZ")
    service._load_events("000001.SZ")

    datasets = {item["dataset"] for item in recorded}
    assert datasets == {"company_profile", "financial_summary", "price_daily", "event"}
    assert all(item["success"] is True for item in recorded)
    assert all(item["records_written"] >= 1 for item in recorded)


def test_prices_choose_highest_priority_runtime_source() -> None:
    class FakeRepository:
        def __init__(self):
            self.prices = []

        def list_prices(self, ticker: str, limit: int = 60, start_date=None, end_date=None):
            return self.prices

        def upsert_prices(self, ticker: str, prices):
            self.prices = prices
            return prices

        def get_last_synced_at(self, dataset: str, ticker: str):
            return None

        def get_sync_state(self, dataset: str, ticker: str):
            return None

    class FakeAKShareCollector:
        def fetch_daily_prices(self, ticker: str, limit: int = 60, start_date=None, end_date=None):
            return [{"trade_date": "20260317", "close": 10.1, "source": "akshare"}]

    class FakeTushareCollector:
        def fetch_daily_prices(self, ticker: str, limit: int = 60, start_date=None, end_date=None):
            return [{"trade_date": "20260317", "close": 10.5, "source": "tushare"}]

    service = StockDataService(
        repository=FakeRepository(),
        akshare_collector=FakeAKShareCollector(),
        tushare_collector=FakeTushareCollector(),
    )

    prices, status, debug = service._load_prices("000001.SZ")

    assert prices[0].source == "tushare"
    assert prices[0].close == 10.5
    assert status.source == "tushare"
    assert status.source_metadata.fallback_used is True
    assert status.source_metadata.selection_reason == "highest_source_priority"
    assert [item.source for item in debug] == ["akshare", "tushare"]


def test_prices_successful_refresh_uses_new_updated_at_and_preserves_partial_sync_state() -> None:
    recorded = []

    class FakeRepository:
        def __init__(self):
            self.prices = []

        def list_prices(self, ticker: str, limit: int = 60, start_date=None, end_date=None):
            return self.prices

        def upsert_prices(self, ticker: str, prices):
            self.prices = [
                PriceDaily(
                    ticker=price.ticker,
                    trade_date=price.trade_date,
                    dedupe_key=price.dedupe_key,
                    close=price.close,
                    source=price.source,
                    source_priority=price.source_priority,
                    updated_at="2099-03-20T00:00:00Z",
                )
                for price in prices
            ]
            return self.prices

        def get_last_synced_at(self, dataset: str, ticker: str):
            return "2026-03-10T00:00:00Z"

        def get_sync_state(self, dataset: str, ticker: str):
            return {"status": "ok", "last_synced_at": "2026-03-10T00:00:00Z", "last_success_at": "2026-03-10T00:00:00Z", "last_error_at": None, "last_error_message": None}

        def record_sync_result(self, dataset: str, ticker: str, synced_at: str, **kwargs):
            recorded.append({"dataset": dataset, **kwargs})

    class FakeAKShareCollector:
        def fetch_daily_prices(self, ticker: str, limit: int = 60, start_date=None, end_date=None):
            return [{"trade_date": "20260320", "close": 10.1, "source": "akshare"}]

    class BrokenTushareCollector:
        def fetch_daily_prices(self, ticker: str, limit: int = 60, start_date=None, end_date=None):
            raise RuntimeError("tushare timeout")

    service = StockDataService(
        repository=FakeRepository(),
        akshare_collector=FakeAKShareCollector(),
        tushare_collector=BrokenTushareCollector(),
    )

    prices, status, _ = service._load_prices("000001.SZ", refresh=True)

    assert prices[0].updated_at == "2099-03-20T00:00:00Z"
    assert status.updated_at == "2099-03-20T00:00:00Z"
    assert status.status == "partial"
    assert recorded[0]["success"] is True
    assert recorded[0]["error_message"] == "tushare timeout"


def test_events_expose_mixed_source_metadata_after_runtime_aggregation() -> None:
    class FakeRepository:
        def __init__(self):
            self.events = []

        def list_events(self, ticker: str, limit: int = 20):
            return self.events

        def replace_events(self, ticker: str, events):
            self.events = events
            return events

        def upsert_events(self, ticker: str, events):
            self.events = events
            return events

        def get_last_synced_at(self, dataset: str, ticker: str):
            return None

        def get_sync_state(self, dataset: str, ticker: str):
            return None

        def get_company_profile(self, ticker: str):
            return None

        def upsert_company_profile(self, profile):
            return profile

    class FakeCNInfoCollector:
        def fetch_events(self, ticker: str, limit: int = 20):
            return [{"announcementId": "ann-1", "announcementTitle": "关于年报的公告", "announcementTime": "2026-03-16", "adjunctUrl": "/same.pdf"}]

    class FakeExchangeSearchCollector:
        def fetch_events_with_debug(self, ticker: str, company_name: str | None = None, limit: int = 10):
            return {
                "items": [{
                    "event_id": "search-1",
                    "dedupe_key": "000001.SZ:shared-key",
                    "ticker": ticker,
                    "event_date": "2026-03-16",
                    "title": "关于年报的公告",
                    "raw_title": "关于年报的公告",
                    "event_type": "financial_report",
                    "category": "exchange_disclosure",
                    "sentiment": "neutral",
                    "source_type": "exchange_search",
                    "source": "exchange_search",
                    "source_priority": 60,
                    "url": "https://www.szse.cn/disclosure/shared",
                    "source_url": "https://www.szse.cn/disclosure/shared",
                    "summary": "exchange result",
                    "importance": "high",
                }],
                "debug": {"source": "exchange_search", "status": "ok", "count": 1, "kept_count": 1, "error": None},
            }

    service = StockDataService(
        repository=FakeRepository(),
        cninfo_collector=FakeCNInfoCollector(),
        exchange_search_collector=FakeExchangeSearchCollector(),
        tushare_collector=type("FakeTushareCollector", (), {"fetch_company_profile": lambda self, ticker: {"basic": {"name": "平安银行"}, "company": {}}})(),
    )

    events, status, _ = service._load_events("000001.SZ")

    assert len(events) == 2
    assert status.source_metadata.selected_source == "cninfo"
    assert "cninfo" in status.source_metadata.returned_sources
    assert "exchange_search" in status.source_metadata.returned_sources


def test_events_successful_refresh_uses_new_updated_at_and_preserves_partial_sync_state() -> None:
    recorded = []

    class FakeRepository:
        def __init__(self):
            self.events = []

        def list_events(self, ticker: str, limit: int = 20):
            return self.events

        def upsert_events(self, ticker: str, events):
            self.events = [
                Event(
                    event_id=event.event_id,
                    dedupe_key=event.dedupe_key,
                    ticker=event.ticker,
                    event_date=event.event_date,
                    title=event.title,
                    raw_title=event.raw_title,
                    event_type=event.event_type,
                    category=event.category,
                    sentiment=event.sentiment,
                    source_type=event.source_type,
                    source=event.source,
                    source_priority=event.source_priority,
                    url=event.url,
                    source_url=event.source_url,
                    summary=event.summary,
                    importance=event.importance,
                    updated_at="2099-03-20T00:00:00Z",
                )
                for event in events
            ]
            return self.events

        def replace_events(self, ticker: str, events):
            return self.upsert_events(ticker, events)

        def get_last_synced_at(self, dataset: str, ticker: str):
            return "2026-03-10T00:00:00Z"

        def get_sync_state(self, dataset: str, ticker: str):
            return {"status": "ok", "last_synced_at": "2026-03-10T00:00:00Z", "last_success_at": "2026-03-10T00:00:00Z", "last_error_at": None, "last_error_message": None}

        def get_company_profile(self, ticker: str):
            return None

        def upsert_company_profile(self, profile):
            return profile

        def record_sync_result(self, dataset: str, ticker: str, synced_at: str, **kwargs):
            recorded.append({"dataset": dataset, **kwargs})

    class FakeCNInfoCollector:
        def fetch_events(self, ticker: str, limit: int = 20):
            return [{"announcementTitle": "关于年报的公告", "announcementTime": "2026-03-20", "adjunctUrl": "finalpage/test.pdf"}]

    class BrokenExchangeSearchCollector:
        def fetch_events_with_debug(self, ticker: str, company_name: str | None = None, limit: int = 10):
            raise RuntimeError("exchange search timeout")

    service = StockDataService(
        repository=FakeRepository(),
        cninfo_collector=FakeCNInfoCollector(),
        exchange_search_collector=BrokenExchangeSearchCollector(),
        tushare_collector=type("FakeTushareCollector", (), {"fetch_company_profile": lambda self, ticker: {"basic": {"name": "平安银行"}, "company": {}}})(),
    )

    events, status, _ = service._load_events("000001.SZ", refresh=True)

    assert events[0].updated_at == "2099-03-20T00:00:00Z"
    assert status.updated_at == "2099-03-20T00:00:00Z"
    assert status.status == "partial"
    event_record = next(item for item in recorded if item["dataset"] == "event")
    assert event_record["success"] is True
    assert event_record["error_message"] == "exchange search timeout"
