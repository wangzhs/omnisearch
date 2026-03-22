from app.models.stock import Event
from app.models.stock import FinancialSummary, PriceDaily
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
