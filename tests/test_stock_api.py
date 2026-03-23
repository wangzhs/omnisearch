import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.stock import CompanyOverview, OverviewDebugResponse, SourcesHealthResponse, SyncHealthResponse
from app.normalizers.stock import normalize_price_daily
from app.schemas.search import SearchResult

SNAPSHOT_DIR = Path(__file__).parent / "snapshots"


def assert_matches_snapshot(name: str, payload: dict) -> None:
    expected = json.loads((SNAPSHOT_DIR / name).read_text(encoding="utf-8"))
    assert payload == expected


class FakeStockService:
    @staticmethod
    def _debug_payload(
        endpoint: str,
        *,
        sources: list[dict] | None = None,
        sections: dict | None = None,
        pagination: dict | None = None,
    ):
        return {
            "endpoint": endpoint,
            "sources": sources or [],
            "sections": sections or {},
            "pagination": pagination,
        }

    @staticmethod
    def _data_status(
        source: str | None,
        *,
        status: str = "fresh",
        fallback_used: bool = False,
        attempted_sources: list[str] | None = None,
        last_error_message: str | None = None,
        last_error_at: str | None = None,
    ):
        return {
            "status": status,
            "updated_at": "2026-03-17T00:00:00Z" if status != "missing" else None,
            "source": source,
            "ttl_hours": 24,
            "cache_hit": True if status != "missing" else False,
            "error_message": last_error_message,
            "last_synced_at": "2026-03-17T00:00:00Z" if status != "missing" else None,
            "last_success_at": "2026-03-17T00:00:00Z" if status != "missing" else None,
            "last_error_at": last_error_at,
            "last_error_message": last_error_message,
            "source_metadata": {
                "selected_source": source,
                "selected_source_priority": None if source is None else {"tushare": 100, "cninfo": 100, "akshare": 90, "exchange_search": 60, "fallback": 10, "derived": 0}.get(source, 0),
                "fallback_used": fallback_used,
                "attempted_sources": attempted_sources or ([source] if source else []),
                "returned_sources": [source] if source else [],
                "selection_reason": "test-fixture",
                "fallback_reason": last_error_message if fallback_used else None,
            },
        }

    def get_company(self, ticker: str, refresh: bool = False):
        return {
            "ticker": "000001.SZ",
            "name": "Ping An Bank",
            "exchange": "SZSE",
            "market": "Main Board",
            "industry": "Bank",
            "area": "Guangdong",
            "list_date": "1991-04-03",
            "status": "L",
            "website": "https://bank.pingan.com",
            "chairman": None,
            "manager": None,
            "employees": None,
            "main_business": None,
            "business_scope": None,
            "source": "tushare",
            "source_priority": 100,
            "updated_at": "2026-03-17T00:00:00Z",
            "raw": {},
        }

    def list_events(self, ticker: str, limit: int = 20, refresh: bool = False):
        return [
            {
                "event_id": "evt-1",
                "ticker": "000001.SZ",
                "dedupe_key": "evt-1",
                "event_date": "2026-03-16",
                "title": "Annual report disclosed",
                "raw_title": "Annual report disclosed",
                "event_type": "financial_report",
                "category": "report",
                "sentiment": "neutral",
                "source_type": "filing",
                "source": "cninfo",
                "source_priority": 100,
                "url": "https://example.com/report.pdf",
                "source_url": "https://example.com/report.pdf",
                "summary": "Annual report filing",
                "updated_at": "2026-03-17T00:00:00Z",
                "importance": "high",
                "raw": {},
            }
        ]

    def list_financials(self, ticker: str, limit: int = 8, refresh: bool = False):
        return [
            {
                "record_id": "000001.SZ:2025-12-31:annual",
                "ticker": "000001.SZ",
                "report_date": "2025-12-31",
                "announcement_date": "2026-03-16",
                "report_type": "annual",
                "revenue": 100.0,
                "revenue_yoy": -2.0,
                "net_profit": -5.0,
                "net_profit_yoy": -10.0,
                "eps": 0.2,
                "roe": 1.0,
                "gross_margin": 30.0,
                "source": "tushare",
                "source_priority": 100,
                "updated_at": "2026-03-17T00:00:00Z",
                "raw": {},
            }
        ]

    def list_financials_with_debug(self, ticker: str, limit: int = 8, refresh: bool = False):
        return {
            "ticker": "000001.SZ",
            "items": self.list_financials(ticker, limit=limit, refresh=refresh),
            "data_status": self._data_status("tushare", attempted_sources=["tushare"]),
            "debug": self._debug_payload(
                "financial_summary",
                sources=[{"source": "tushare", "status": "ok", "count": 1, "kept_count": 1, "error": None}],
            ),
        }

    def list_prices(
        self,
        ticker: str,
        limit: int = 60,
        start_date: str | None = None,
        end_date: str | None = None,
        refresh: bool = False,
    ):
        return [
            {
                "ticker": "000001.SZ",
                "trade_date": "2026-03-13",
                "open": 10.0,
                "high": 11.0,
                "low": 9.9,
                "close": 10.8,
                "volume": 1000.0,
                "amount": 5000.0,
                "change_pct": 9.5,
                "turnover_rate": 2.0,
                "source": "akshare",
                "source_priority": 90,
                "updated_at": "2026-03-17T00:00:00Z",
                "raw": {},
            }
        ]

    def get_overview(self, ticker: str, refresh: bool = False):
        return {
            "ticker": "000001.SZ",
            "company": {
                "data": self.get_company(ticker, refresh=refresh),
                "data_status": self._data_status("tushare", attempted_sources=["tushare"]),
            },
            "latest_financial": {
                "data": self.list_financials(ticker, refresh=refresh)[0],
                "data_status": self._data_status("tushare", attempted_sources=["tushare"]),
            },
            "latest_price": {
                "data": self.list_prices(ticker, refresh=refresh)[0],
                "data_status": self._data_status("akshare", attempted_sources=["akshare", "tushare"]),
            },
            "recent_events": {
                "data": self.list_events(ticker, refresh=refresh),
                "data_status": self._data_status("cninfo", attempted_sources=["cninfo", "exchange_search"]),
            },
            "risk_flags": {
                "data": self.get_risk_flags(ticker, refresh=refresh),
                "data_status": self._data_status("derived", attempted_sources=["derived"]),
            },
            "signals": {
                "data": [
                    {
                        "code": "profitability",
                        "label": "Profitability",
                        "value": "negative",
                        "importance": "high",
                        "direction": "negative",
                        "evidence": "Latest reported net profit is below zero.",
                    }
                ],
                "data_status": self._data_status("derived", attempted_sources=["derived"]),
            },
        }

    def get_company_with_debug(self, ticker: str, refresh: bool = False):
        return {
            "ticker": "000001.SZ",
            "data": self.get_company(ticker, refresh=refresh),
            "data_status": self._data_status("tushare", attempted_sources=["tushare"]),
            "debug": self._debug_payload(
                "company_profile",
                sources=[{"source": "tushare", "status": "ok", "count": 1, "kept_count": 1, "error": None}],
            ),
        }

    def get_overview_with_debug(self, ticker: str, refresh: bool = False):
        overview = self.get_overview(ticker, refresh=refresh)
        return {
            "ticker": "000001.SZ",
            "data": overview,
            "data_status": self._data_status("derived", attempted_sources=["derived"]),
            "debug": self._debug_payload(
                "company_overview",
                sections={
                    "company": {
                        "data_status": overview["company"]["data_status"],
                        "sources": [{"source": "tushare", "status": "ok", "count": 1, "kept_count": 1, "error": None}],
                    },
                    "latest_financial": {
                        "data_status": overview["latest_financial"]["data_status"],
                        "sources": [{"source": "tushare", "status": "ok", "count": 1, "kept_count": 1, "error": None}],
                    },
                    "latest_price": {
                        "data_status": overview["latest_price"]["data_status"],
                        "sources": [{"source": "akshare", "status": "ok", "count": 1, "kept_count": 1, "error": None}],
                    },
                    "recent_events": {
                        "data_status": overview["recent_events"]["data_status"],
                        "sources": [{"source": "cninfo", "status": "ok", "count": 1, "kept_count": 1, "error": None}],
                    },
                    "risk_flags": {
                        "data_status": overview["risk_flags"]["data_status"],
                        "sources": [{"source": "derived", "status": "ok", "count": 1, "kept_count": 1, "error": None}],
                    },
                    "signals": {
                        "data_status": overview["signals"]["data_status"],
                        "sources": [{"source": "derived", "status": "ok", "count": 1, "kept_count": 1, "error": None}],
                    },
                },
            ),
        }

    def get_timeline(self, ticker: str, refresh: bool = False):
        return [
            {
                "date": "2026-03-16",
                "kind": "event",
                "title": "Annual report disclosed",
                "summary": "Annual report filing",
                "url": "https://example.com/report.pdf",
                "source": "cninfo",
            }
        ]

    def get_risk_flags(self, ticker: str, refresh: bool = False):
        return [
            {"level": "high", "code": "negative_net_profit", "message": "Latest reported net profit is negative."}
        ]

    def get_research_context(self, ticker: str, refresh: bool = False):
        return {
            "ticker": "000001.SZ",
            "company": self.get_company(ticker, refresh=refresh),
            "recent_events": self.list_events(ticker, refresh=refresh),
            "latest_financial": self.list_financials(ticker, refresh=refresh)[0],
            "latest_price": self.list_prices(ticker, refresh=refresh)[0],
            "risk_flags": self.get_risk_flags(ticker, refresh=refresh),
        }


def test_company_overview_endpoint_returns_stock_snapshot(monkeypatch) -> None:
    monkeypatch.setattr("app.api.routes.get_stock_data_service", lambda: FakeStockService())

    client = TestClient(app)
    response = client.get("/company/000001/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "000001.SZ"
    assert payload["company"]["data"]["ticker"] == "000001.SZ"
    assert payload["latest_financial"]["data"]["net_profit"] == -5.0
    assert payload["risk_flags"]["data"][0]["code"] == "negative_net_profit"
    assert payload["company"]["data_status"]["status"] == "fresh"
    assert payload["recent_events"]["data_status"]["source"] == "cninfo"
    assert payload["recent_events"]["data"][0]["source_priority"] == 100
    assert payload["latest_price"]["data_status"]["source_metadata"]["attempted_sources"] == ["akshare", "tushare"]
    assert payload["latest_price"]["data"]["source_priority"] == 90
    assert "raw" not in payload["company"]["data"]
    assert "raw" not in payload["latest_financial"]["data"]
    assert "raw" not in payload["latest_price"]["data"]
    assert_matches_snapshot("company_overview_fresh.json", payload)


def test_company_overview_contract_has_data_status_for_every_section() -> None:
    example = CompanyOverview.model_config["json_schema_extra"]["example"]

    assert example["ticker"] == "000001.SZ"
    for section in ("company", "latest_financial", "latest_price", "recent_events", "risk_flags", "signals"):
        assert "data" in example[section]
        assert "data_status" in example[section]


def test_overview_debug_schema_example_tracks_stable_contract() -> None:
    example = OverviewDebugResponse.model_config["json_schema_extra"]["example"]

    assert example["debug"]["endpoint"] == "company_overview"
    assert set(example["debug"]["sections"]) == {"company", "latest_financial", "latest_price", "recent_events", "risk_flags", "signals"}
    assert example["data_status"]["status"] == "partial"
    assert example["data_status"]["source_metadata"]["selected_source"] == "derived"
    assert example["data_status"]["source_metadata"]["attempted_sources"] == ["derived"]
    assert example["debug"]["sections"]["latest_financial"]["data_status"]["source_metadata"]["attempted_sources"] == ["tushare"]
    assert example["debug"]["sections"]["latest_financial"]["data_status"]["status"] == "partial"


def test_company_overview_falls_back_when_company_profile_missing(monkeypatch) -> None:
    class PartialStockService(FakeStockService):
        def get_overview(self, ticker: str, refresh: bool = False):
            return {
                "ticker": "002837.SZ",
                "company": {
                    "data": {
                        "ticker": "002837.SZ",
                        "name": None,
                        "exchange": None,
                        "market": None,
                        "industry": None,
                        "area": None,
                        "list_date": None,
                        "status": "unknown",
                        "website": None,
                        "chairman": None,
                        "manager": None,
                        "employees": None,
                        "main_business": None,
                        "business_scope": None,
                        "source": "fallback",
                        "updated_at": None,
                        "raw": {},
                    },
                    "data_status": {
                        **self._data_status("tushare", status="missing", attempted_sources=["tushare"]),
                        "cache_hit": False,
                    },
                },
                "latest_financial": {"data": self.list_financials(ticker, refresh=refresh)[0], "data_status": self._data_status("tushare", attempted_sources=["tushare"])},
                "latest_price": {"data": self.list_prices(ticker, refresh=refresh)[0], "data_status": self._data_status("akshare", attempted_sources=["akshare", "tushare"])},
                "recent_events": {"data": self.list_events(ticker, refresh=refresh), "data_status": self._data_status("cninfo", attempted_sources=["cninfo", "exchange_search"])},
                "risk_flags": {"data": self.get_risk_flags(ticker, refresh=refresh), "data_status": self._data_status("derived", attempted_sources=["derived"])},
                "signals": {"data": [], "data_status": self._data_status("derived", attempted_sources=["derived"])},
            }

    monkeypatch.setattr("app.api.routes.get_stock_data_service", lambda: PartialStockService())

    client = TestClient(app)
    response = client.get("/company/002837/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["company"]["data"]["ticker"] == "002837.SZ"
    assert payload["company"]["data"]["source"] == "fallback"
    assert payload["company"]["data_status"]["status"] == "missing"
    assert_matches_snapshot("company_overview_missing_company.json", payload)


def test_company_overview_exposes_stale_failed_snapshot(monkeypatch) -> None:
    class StaleStockService(FakeStockService):
        def get_overview(self, ticker: str, refresh: bool = False):
            return {
                "ticker": "600036.SH",
                "company": {
                    "data": {
                        "ticker": "600036.SH",
                        "name": "China Merchants Bank",
                        "source": "tushare",
                        "source_priority": 100,
                        "updated_at": "2026-03-10T00:00:00Z",
                    },
                    "data_status": self._data_status(
                        "tushare",
                        status="stale",
                        attempted_sources=["tushare"],
                        last_error_message="Upstream request timed out.",
                        last_error_at="2026-03-17T00:00:00Z",
                    ),
                },
                "latest_financial": {"data": None, "data_status": self._data_status("tushare", status="stale", attempted_sources=["tushare"])},
                "latest_price": {
                    "data": None,
                    "data_status": self._data_status(
                        "akshare",
                        status="failed",
                        attempted_sources=["akshare", "tushare"],
                        last_error_message="eastmoney unavailable",
                        last_error_at="2026-03-17T00:00:00Z",
                    ),
                },
                "recent_events": {"data": [], "data_status": self._data_status(None, status="missing", attempted_sources=["cninfo", "exchange_search"])},
                "risk_flags": {
                    "data": [],
                    "data_status": self._data_status(
                        "derived",
                        status="failed",
                        attempted_sources=["derived"],
                        last_error_message="Dependent sections are incomplete.",
                        last_error_at="2026-03-17T00:00:00Z",
                    ),
                },
                "signals": {
                    "data": [],
                    "data_status": self._data_status(
                        "derived",
                        status="failed",
                        attempted_sources=["derived"],
                        last_error_message="Dependent sections are incomplete.",
                        last_error_at="2026-03-17T00:00:00Z",
                    ),
                },
            }

    monkeypatch.setattr("app.api.routes.get_stock_data_service", lambda: StaleStockService())

    client = TestClient(app)
    response = client.get("/company/600036/overview")

    assert response.status_code == 200
    assert_matches_snapshot("company_overview_stale_failed.json", response.json())


def test_company_overview_exposes_partial_source_priority_snapshot(monkeypatch) -> None:
    class PartialOverviewService(FakeStockService):
        def get_overview(self, ticker: str, refresh: bool = False):
            return {
                "ticker": "002837.SZ",
                "company": {"data": self.get_company(ticker, refresh=refresh), "data_status": self._data_status("tushare", attempted_sources=["tushare"])},
                "latest_financial": {"data": self.list_financials(ticker, refresh=refresh)[0], "data_status": self._data_status("tushare", attempted_sources=["tushare"])},
                "latest_price": {
                    "data": {**self.list_prices(ticker, refresh=refresh)[0], "source": "tushare", "source_priority": 100},
                    "data_status": self._data_status("tushare", fallback_used=True, attempted_sources=["akshare", "tushare"]),
                },
                "recent_events": {
                    "data": [{
                        "event_id": "evt-fallback",
                        "ticker": "002837.SZ",
                        "dedupe_key": "evt-fallback",
                        "event_date": "2026-03-16",
                        "title": "英维克 年报公告",
                        "raw_title": "英维克 年报公告",
                        "event_type": "financial_report",
                        "category": "exchange_disclosure",
                        "sentiment": "neutral",
                        "source_type": "exchange_search",
                        "source": "exchange_search",
                        "source_priority": 60,
                        "url": "https://www.szse.cn/disclosure/test",
                        "source_url": "https://www.szse.cn/disclosure/test",
                        "summary": "Fallback event source",
                        "updated_at": "2026-03-17T00:00:00Z",
                        "importance": "high",
                    }],
                    "data_status": self._data_status("exchange_search", fallback_used=True, attempted_sources=["cninfo", "exchange_search"]),
                },
                "risk_flags": {"data": self.get_risk_flags(ticker, refresh=refresh), "data_status": self._data_status("derived", attempted_sources=["derived"])},
                "signals": {"data": [], "data_status": self._data_status("derived", attempted_sources=["derived"])},
            }

    monkeypatch.setattr("app.api.routes.get_stock_data_service", lambda: PartialOverviewService())

    client = TestClient(app)
    response = client.get("/company/002837/overview")

    assert response.status_code == 200
    assert_matches_snapshot("company_overview_partial.json", response.json())


def test_company_debug_endpoint_returns_data_status(monkeypatch) -> None:
    monkeypatch.setattr("app.api.routes.get_stock_data_service", lambda: FakeStockService())

    client = TestClient(app)
    response = client.get("/company/000001?debug=true")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "000001.SZ"
    assert payload["data"]["source_priority"] == 100
    assert payload["data_status"]["status"] == "fresh"
    assert payload["debug"]["endpoint"] == "company_profile"
    assert payload["debug"]["sources"][0]["status"] == "ok"
    assert payload["data_status"]["source_metadata"]["selection_reason"] == "test-fixture"


def test_company_overview_debug_is_main_observability_entrypoint(monkeypatch) -> None:
    monkeypatch.setattr("app.api.routes.get_stock_data_service", lambda: FakeStockService())

    client = TestClient(app)
    response = client.get("/company/000001/overview?debug=true")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "000001.SZ"
    assert payload["data"]["ticker"] == "000001.SZ"
    assert payload["data_status"]["source"] == "derived"
    assert payload["debug"]["endpoint"] == "company_overview"
    assert set(payload["debug"]["sections"]) == {"company", "latest_financial", "latest_price", "recent_events", "risk_flags", "signals"}
    assert payload["data_status"]["status"] == payload["debug"]["sections"]["risk_flags"]["data_status"]["status"]
    assert payload["data_status"]["source_metadata"]["returned_sources"] == ["derived"]
    assert payload["debug"]["sections"]["latest_price"]["data_status"]["source"] == "akshare"
    assert payload["debug"]["sections"]["recent_events"]["sources"][0]["source"] == "cninfo"
    assert payload["debug"]["sections"]["risk_flags"]["data_status"]["source_metadata"]["returned_sources"] == ["derived"]
    assert payload["debug"]["sections"]["signals"]["data_status"]["source_metadata"]["returned_sources"] == ["derived"]


def test_company_overview_debug_uses_helper_specific_selection_reasons(monkeypatch) -> None:
    from app.services.stock import StockDataService

    class DerivedMetadataService(StockDataService):
        def __init__(self):
            super().__init__(repository=type("Repo", (), {})())

        def _load_company(self, ticker: str, refresh: bool = False):
            return (
                self._build_placeholder_company(ticker),
                self._build_data_status(source="tushare", updated_at="2099-01-01T00:00:00Z", cache_hit=True),
            )

        def _load_financials(self, ticker: str, limit: int = 8, refresh: bool = False):
            return (
                [],
                self._build_data_status(
                    source="tushare",
                    updated_at="2099-01-01T00:00:00Z",
                    cache_hit=True,
                    partial=True,
                    error_message="financial retry pending",
                ),
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

    monkeypatch.setattr("app.api.routes.get_stock_data_service", lambda: DerivedMetadataService())

    client = TestClient(app)
    response = client.get("/company/000001/overview?debug=true")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data_status"]["source_metadata"]["selection_reason"] == "overview_rollup"
    assert payload["debug"]["sections"]["risk_flags"]["data_status"]["source_metadata"]["selection_reason"] == "risk_flags_rollup"
    assert payload["debug"]["sections"]["signals"]["data_status"]["source_metadata"]["selection_reason"] == "signals_rollup"


def test_company_overview_debug_rolls_up_stale_and_failed_section_states(monkeypatch) -> None:
    class BoundaryOverviewService(FakeStockService):
        def get_overview_with_debug(self, ticker: str, refresh: bool = False):
            overview = self.get_overview(ticker, refresh=refresh)
            return {
                "ticker": "000001.SZ",
                "data": overview,
                "data_status": self._data_status("derived", status="failed", attempted_sources=["derived"], last_error_message="latest price unavailable"),
                "debug": self._debug_payload(
                    "company_overview",
                    sections={
                        "company": {"data_status": self._data_status("tushare", attempted_sources=["tushare"]), "sources": []},
                        "latest_financial": {"data_status": self._data_status("tushare", status="stale", attempted_sources=["tushare"]), "sources": []},
                        "latest_price": {"data_status": self._data_status("akshare", status="failed", attempted_sources=["akshare"], last_error_message="latest price unavailable"), "sources": []},
                        "recent_events": {"data_status": self._data_status("cninfo", attempted_sources=["cninfo"]), "sources": []},
                        "risk_flags": {"data_status": self._data_status("derived", status="failed", attempted_sources=["derived"], last_error_message="latest price unavailable"), "sources": []},
                        "signals": {"data_status": self._data_status("derived", status="failed", attempted_sources=["derived"], last_error_message="latest price unavailable"), "sources": []},
                    },
                ),
            }

    monkeypatch.setattr("app.api.routes.get_stock_data_service", lambda: BoundaryOverviewService())

    client = TestClient(app)
    response = client.get("/company/000001/overview?debug=true")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data_status"]["status"] == "failed"
    assert payload["debug"]["sections"]["latest_financial"]["data_status"]["status"] == "stale"
    assert payload["debug"]["sections"]["latest_price"]["data_status"]["status"] == "failed"
    assert payload["debug"]["sections"]["risk_flags"]["data_status"]["status"] == "failed"


def test_prices_fall_back_to_tushare_when_akshare_fails() -> None:
    class FakeRepository:
        def __init__(self):
            self._prices = []

        def list_prices(self, ticker: str, limit: int = 60, start_date=None, end_date=None):
            return self._prices

        def get_last_synced_at(self, dataset: str, ticker: str):
            return None

        def upsert_prices(self, ticker: str, prices):
            self._prices = prices
            return prices

    class BrokenAKShareCollector:
        def fetch_daily_prices(self, ticker: str, limit: int = 60, start_date=None, end_date=None):
            raise RuntimeError("eastmoney failed")

    class FallbackTushareCollector:
        def fetch_daily_prices(self, ticker: str, limit: int = 60, start_date=None, end_date=None):
            return [
                {
                    "trade_date": "20260317",
                    "open": 10.0,
                    "high": 10.2,
                    "low": 9.9,
                    "close": 10.1,
                    "volume": 1000,
                    "amount": 2000,
                    "change_pct": 1.2,
                    "turnover_rate": 0.5,
                    "source": "tushare",
                }
            ]

    from app.services.stock import StockDataService

    repository = FakeRepository()
    service = StockDataService(
        repository=repository,
        tushare_collector=FallbackTushareCollector(),
        akshare_collector=BrokenAKShareCollector(),
    )

    prices = service.list_prices("000001")

    assert len(prices) == 1
    assert prices[0].trade_date == "2026-03-17"
    assert prices[0].close == 10.1


def test_financials_fall_back_to_cached_rows_when_refresh_returns_empty() -> None:
    class FakeRepository:
        def __init__(self):
            self._items = []

        def list_financial_summaries(self, ticker: str, limit: int = 8):
            return self._items

        def get_last_synced_at(self, dataset: str, ticker: str):
            return None

        def upsert_financial_summaries(self, ticker: str, items):
            self._items = items
            return items

    class EmptyTushareCollector:
        def fetch_financial_summaries(self, ticker: str, limit: int = 8):
            return []

    from app.models.stock import FinancialSummary
    from app.services.stock import StockDataService

    repository = FakeRepository()
    repository._items = [
        FinancialSummary(
            record_id="002837.SZ:2025-09-30:1",
            dedupe_key="002837.SZ:2025-09-30:1",
            ticker="002837.SZ",
            report_date="2025-09-30",
            announcement_date="2025-10-14",
            report_type="1",
            revenue=1.0,
            source="tushare",
        )
    ]
    service = StockDataService(repository=repository, tushare_collector=EmptyTushareCollector())

    items = service.list_financials("002837", refresh=True)

    assert len(items) == 1
    assert items[0].report_date == "2025-09-30"


def test_normalize_price_daily_keeps_source_from_raw_payload() -> None:
    price = normalize_price_daily(
        "002837",
        {
            "trade_date": "20260317",
            "open": 10,
            "high": 11,
            "low": 9,
            "close": 10.5,
            "volume": 123,
            "amount": 456,
            "change_pct": 1.2,
            "turnover_rate": 0.8,
            "source": "tushare",
        },
    )

    assert price.source == "tushare"


def test_company_risk_flags_include_missing_data_signals(monkeypatch) -> None:
    class SparseStockService(FakeStockService):
        def get_risk_flags(self, ticker: str, refresh: bool = False):
            return [
                {
                    "level": "low",
                    "code": "price_data_unavailable",
                    "message": "No recent daily price data is available.",
                    "dimension": "price",
                    "as_of_date": None,
                },
                {
                    "level": "low",
                    "code": "event_data_unavailable",
                    "message": "No recent disclosure events are available.",
                    "dimension": "event",
                    "as_of_date": None,
                },
            ]

    monkeypatch.setattr("app.api.routes.get_stock_data_service", lambda: SparseStockService())

    client = TestClient(app)
    response = client.get("/company/002837/risk-flags")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["dimension"] == "price"
    assert payload[1]["code"] == "event_data_unavailable"


def test_company_timeline_includes_importance(monkeypatch) -> None:
    class TimelineStockService(FakeStockService):
        def get_timeline(self, ticker: str, refresh: bool = False):
            return [
                {
                    "date": "2026-03-17",
                    "kind": "price",
                    "title": "2026-03-17 close 101.28",
                    "summary": "pct_change=-3.62%, turnover=5.69%",
                    "url": None,
                    "source": "tushare",
                    "importance": "medium",
                }
            ]

    monkeypatch.setattr("app.api.routes.get_stock_data_service", lambda: TimelineStockService())

    client = TestClient(app)
    response = client.get("/company/002837/timeline")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["importance"] == "medium"


def test_events_fall_back_to_exchange_search_when_cninfo_is_empty() -> None:
    class FakeRepository:
        def __init__(self):
            self._events = []

        def list_events(self, ticker: str, limit: int = 20):
            return self._events

        def get_company_profile(self, ticker: str):
            return None

        def upsert_company_profile(self, profile):
            return profile

        def get_last_synced_at(self, dataset: str, ticker: str):
            return None

        def upsert_events(self, ticker: str, events):
            self._events = events
            return events

    class EmptyCNInfoCollector:
        def fetch_events(self, ticker: str, limit: int = 20):
            return []

    class FallbackExchangeSearchCollector:
        def fetch_events_with_debug(self, ticker: str, company_name: str | None = None, limit: int = 10):
            return {
                "items": [
                    {
                        "event_id": "https://www.szse.cn/disclosure/test",
                        "dedupe_key": "002837.SZ:test",
                        "ticker": ticker,
                        "event_date": None,
                        "title": "英维克 关于年报的公告",
                        "raw_title": "英维克 关于年报的公告",
                        "event_type": "financial_report",
                        "category": "exchange_disclosure",
                        "sentiment": "neutral",
                        "source_type": "exchange_search",
                        "source": "exchange_search",
                        "url": "https://www.szse.cn/disclosure/test",
                        "summary": "Official exchange disclosure",
                        "importance": "high",
                        "raw": {},
                    }
                ],
                "debug": {
                    "source": "exchange_search",
                    "status": "ok",
                    "count": 1,
                    "kept_count": 1,
                    "error": None,
                },
            }

    class TushareWithCompany:
        def fetch_company_profile(self, ticker: str):
            return {
                "basic": {"name": "英维克", "market": "主板", "industry": "专用机械", "area": "深圳", "list_status": "L"},
                "company": {},
                "ticker": ticker,
            }

    from app.services.stock import StockDataService

    repository = FakeRepository()
    service = StockDataService(
        repository=repository,
        tushare_collector=TushareWithCompany(),
        cninfo_collector=EmptyCNInfoCollector(),
        exchange_search_collector=FallbackExchangeSearchCollector(),
    )

    events = service.list_events("002837")

    assert len(events) == 1
    assert events[0].source == "exchange_search"
    assert "年报" in events[0].title


def test_research_includes_stock_context_for_ticker_queries(monkeypatch) -> None:
    def fake_search_web(query: str, top_k: int, searxng_base_url: str):
        return [SearchResult(title="A", url="https://example.com/a", snippet="s1", source="searxng", score=1.0)]

    def fake_extract_content(url: str):
        return {
            "title": "Extracted",
            "url": url,
            "markdown": f"# {url}",
            "published_date": None,
            "domain": "example.com",
        }

    monkeypatch.setattr("app.api.routes.search_web", fake_search_web)
    monkeypatch.setattr("app.api.routes.extract_content", fake_extract_content)
    monkeypatch.setattr("app.api.routes.get_stock_data_service", lambda: FakeStockService())

    client = TestClient(app)
    response = client.post("/research", json={"query": "000001 业绩", "top_k": 1})

    assert response.status_code == 200
    payload = response.json()
    assert payload["stock_context"]["ticker"] == "000001.SZ"
    assert payload["stock_context"]["latest_price"]["close"] == 10.8


def test_research_ignores_stock_context_failures(monkeypatch) -> None:
    def fake_search_web(query: str, top_k: int, searxng_base_url: str):
        return [SearchResult(title="A", url="https://example.com/a", snippet="s1", source="searxng", score=1.0)]

    def fake_extract_content(url: str):
        return {
            "title": "Extracted",
            "url": url,
            "markdown": f"# {url}",
            "published_date": None,
            "domain": "example.com",
        }

    class BrokenStockService:
        def get_research_context(self, ticker: str, refresh: bool = False):
            raise Exception("token invalid")

    monkeypatch.setattr("app.api.routes.search_web", fake_search_web)
    monkeypatch.setattr("app.api.routes.extract_content", fake_extract_content)
    monkeypatch.setattr("app.api.routes.get_stock_data_service", lambda: BrokenStockService())

    client = TestClient(app)
    response = client.post("/research", json={"query": "000001 业绩", "top_k": 1})

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["extracted"]["domain"] == "example.com"
    assert payload["stock_context"] is None


def test_prices_debug_endpoint_returns_source_status(monkeypatch) -> None:
    class DebugStockService(FakeStockService):
        def list_prices_with_debug(
            self,
            ticker: str,
            limit: int = 60,
            start_date: str | None = None,
            end_date: str | None = None,
            refresh: bool = False,
        ):
            return {
                "ticker": "002837.SZ",
                "items": [],
                "data_status": FakeStockService._data_status("tushare", fallback_used=True, attempted_sources=["akshare", "tushare"]),
                "debug": FakeStockService._debug_payload(
                    "price_daily",
                    sources=[
                        {"source": "akshare", "status": "error", "count": 0, "kept_count": 0, "error": "empty reply"},
                        {"source": "tushare", "status": "empty", "count": 0, "kept_count": 0, "error": None},
                    ],
                ),
            }

    monkeypatch.setattr("app.api.routes.get_stock_data_service", lambda: DebugStockService())

    client = TestClient(app)
    response = client.get("/company/002837/prices?debug=true")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "002837.SZ"
    assert payload["data_status"]["source_metadata"]["fallback_used"] is True
    assert payload["data_status"]["source_metadata"]["returned_sources"] == ["tushare"]
    assert payload["debug"]["endpoint"] == "price_daily"
    assert payload["debug"]["sources"][0]["source"] == "akshare"
    assert payload["debug"]["sources"][1]["status"] == "empty"
    assert payload["debug"]["pagination"]["page"] == 1


def test_events_debug_endpoint_returns_source_status(monkeypatch) -> None:
    class DebugStockService(FakeStockService):
        def list_events_with_debug(self, ticker: str, limit: int = 20, refresh: bool = False):
            return {
                "ticker": "002837.SZ",
                "items": [],
                "data_status": FakeStockService._data_status("exchange_search", fallback_used=True, attempted_sources=["cninfo", "exchange_search"]),
                "debug": FakeStockService._debug_payload(
                    "event",
                    sources=[
                        {"source": "cninfo", "status": "empty", "count": 0, "kept_count": 0, "error": None},
                        {"source": "exchange_search", "status": "ok", "count": 12, "kept_count": 4, "error": None},
                    ],
                ),
            }

    monkeypatch.setattr("app.api.routes.get_stock_data_service", lambda: DebugStockService())

    client = TestClient(app)
    response = client.get("/company/002837/events?debug=true")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "002837.SZ"
    assert payload["data_status"]["source_metadata"]["selected_source"] == "exchange_search"
    assert payload["data_status"]["source_metadata"]["returned_sources"] == ["exchange_search"]
    assert payload["debug"]["endpoint"] == "event"
    assert payload["debug"]["sources"][0]["source"] == "cninfo"
    assert payload["debug"]["sources"][1]["kept_count"] == 4
    assert payload["debug"]["pagination"]["sort_by"] == "event_date"


def test_event_endpoint_supports_filtering_and_pagination(monkeypatch) -> None:
    class FilterStockService(FakeStockService):
        def list_events(self, ticker: str, limit: int = 20, refresh: bool = False):
            return super().list_events(ticker, limit, refresh) + [
                {
                    "event_id": "evt-2",
                    "ticker": "000001.SZ",
                    "event_date": "2026-03-15",
                    "title": "Share buyback plan",
                    "raw_title": "Share buyback plan",
                    "event_type": "capital_operation",
                    "category": "buyback",
                    "sentiment": "positive",
                    "source_type": "filing",
                    "source": "cninfo",
                    "url": None,
                    "summary": "Buyback plan",
                    "updated_at": "2026-03-17T00:00:00Z",
                    "importance": "medium",
                }
            ]

    monkeypatch.setattr("app.api.routes.get_stock_data_service", lambda: FilterStockService())
    client = TestClient(app)

    response = client.get("/company/000001/events?importance=medium&page=1&page_size=1")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["event_id"] == "evt-2"


def test_financials_endpoint_supports_filtering_sorting_and_pagination(monkeypatch) -> None:
    class FinancialStockService(FakeStockService):
        def list_financials(self, ticker: str, limit: int = 8, refresh: bool = False):
            return [
                {
                    "record_id": "000001.SZ:2025-12-31:annual",
                    "ticker": "000001.SZ",
                    "report_date": "2025-12-31",
                    "announcement_date": "2026-03-16",
                    "report_type": "annual",
                    "revenue": 100.0,
                    "revenue_yoy": 1.0,
                    "net_profit": 10.0,
                    "net_profit_yoy": 2.0,
                    "eps": 0.2,
                    "roe": 1.0,
                    "gross_margin": 30.0,
                    "source": "tushare",
                    "updated_at": "2026-03-17T00:00:00Z",
                },
                {
                    "record_id": "000001.SZ:2025-09-30:quarterly",
                    "ticker": "000001.SZ",
                    "report_date": "2025-09-30",
                    "announcement_date": "2025-10-20",
                    "report_type": "quarterly",
                    "revenue": 80.0,
                    "revenue_yoy": 3.0,
                    "net_profit": 8.0,
                    "net_profit_yoy": 4.0,
                    "eps": 0.1,
                    "roe": 0.9,
                    "gross_margin": 28.0,
                    "source": "tushare",
                    "updated_at": "2025-10-21T00:00:00Z",
                },
                {
                    "record_id": "000001.SZ:2025-06-30:quarterly",
                    "ticker": "000001.SZ",
                    "report_date": "2025-06-30",
                    "announcement_date": "2025-07-20",
                    "report_type": "quarterly",
                    "revenue": 70.0,
                    "revenue_yoy": 5.0,
                    "net_profit": 7.0,
                    "net_profit_yoy": 6.0,
                    "eps": 0.09,
                    "roe": 0.8,
                    "gross_margin": 27.0,
                    "source": "tushare",
                    "updated_at": "2025-07-21T00:00:00Z",
                },
            ]

    monkeypatch.setattr("app.api.routes.get_stock_data_service", lambda: FinancialStockService())
    client = TestClient(app)

    response = client.get("/company/000001/financials?report_type=quarterly&sort_order=asc&page=1&page_size=1")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["report_type"] == "quarterly"
    assert payload[0]["report_date"] == "2025-06-30"


def test_financials_endpoint_supports_numeric_sorting(monkeypatch) -> None:
    class FinancialStockService(FakeStockService):
        def list_financials(self, ticker: str, limit: int = 8, refresh: bool = False):
            return [
                {
                    "record_id": "a",
                    "ticker": "000001.SZ",
                    "report_date": "2025-12-31",
                    "announcement_date": "2026-03-16",
                    "report_type": "annual",
                    "revenue": 100.0,
                    "net_profit": 10.0,
                    "source": "tushare",
                    "source_priority": 100,
                    "updated_at": "2026-03-17T00:00:00Z",
                },
                {
                    "record_id": "b",
                    "ticker": "000001.SZ",
                    "report_date": "2025-09-30",
                    "announcement_date": "2025-10-20",
                    "report_type": "quarterly",
                    "revenue": 90.0,
                    "net_profit": 12.0,
                    "source": "tushare",
                    "source_priority": 100,
                    "updated_at": "2025-10-21T00:00:00Z",
                },
            ]

    monkeypatch.setattr("app.api.routes.get_stock_data_service", lambda: FinancialStockService())
    client = TestClient(app)

    response = client.get("/company/000001/financials?sort_by=net_profit&sort_order=desc")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["record_id"] == "b"


def test_financials_debug_endpoint_returns_data_status(monkeypatch) -> None:
    class FinancialDebugStockService(FakeStockService):
        def list_financials_with_debug(self, ticker: str, limit: int = 8, refresh: bool = False):
            return {
                "ticker": "000001.SZ",
                "items": self.list_financials(ticker, limit=limit, refresh=refresh),
                "data_status": FakeStockService._data_status(
                    "tushare",
                    status="partial",
                    attempted_sources=["tushare"],
                    last_error_message="latest annual report retry pending",
                ),
                "debug": FakeStockService._debug_payload(
                    "financial_summary",
                    sources=[{"source": "tushare", "status": "partial", "count": 1, "kept_count": 1, "error": "latest annual report retry pending"}],
                ),
            }

    monkeypatch.setattr("app.api.routes.get_stock_data_service", lambda: FinancialDebugStockService())
    client = TestClient(app)

    response = client.get("/company/000001/financials?debug=true")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "000001.SZ"
    assert payload["data_status"]["status"] == "partial"
    assert payload["data_status"]["last_error_message"] == "latest annual report retry pending"
    assert payload["debug"]["endpoint"] == "financial_summary"
    assert payload["debug"]["sources"][0]["status"] == "partial"
    assert payload["items"][0]["source_priority"] == 100


def test_prices_endpoint_supports_filtering_sorting_and_pagination(monkeypatch) -> None:
    class PriceStockService(FakeStockService):
        def list_prices(
            self,
            ticker: str,
            limit: int = 60,
            start_date: str | None = None,
            end_date: str | None = None,
            refresh: bool = False,
        ):
            return [
                {
                    "ticker": "000001.SZ",
                    "trade_date": "2026-03-13",
                    "open": 10.0,
                    "high": 11.0,
                    "low": 9.9,
                    "close": 10.8,
                    "volume": 1000.0,
                    "amount": 5000.0,
                    "change_pct": 9.5,
                    "turnover_rate": 2.0,
                    "source": "akshare",
                    "updated_at": "2026-03-17T00:00:00Z",
                },
                {
                    "ticker": "000001.SZ",
                    "trade_date": "2026-03-12",
                    "open": 10.0,
                    "high": 10.5,
                    "low": 9.8,
                    "close": 10.1,
                    "volume": 900.0,
                    "amount": 4000.0,
                    "change_pct": 1.5,
                    "turnover_rate": 1.5,
                    "source": "akshare",
                    "updated_at": "2026-03-16T00:00:00Z",
                },
                {
                    "ticker": "000001.SZ",
                    "trade_date": "2026-03-11",
                    "open": 9.8,
                    "high": 10.1,
                    "low": 9.5,
                    "close": 9.6,
                    "volume": 800.0,
                    "amount": 3500.0,
                    "change_pct": -2.0,
                    "turnover_rate": 1.2,
                    "source": "akshare",
                    "updated_at": "2026-03-15T00:00:00Z",
                },
            ]

    monkeypatch.setattr("app.api.routes.get_stock_data_service", lambda: PriceStockService())
    client = TestClient(app)

    response = client.get("/company/000001/prices?min_change_pct=1&sort_order=desc&page=1&page_size=2")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2
    assert payload[0]["trade_date"] == "2026-03-13"
    assert payload[1]["trade_date"] == "2026-03-12"


def test_health_db_returns_repository_backend_status(monkeypatch) -> None:
    class FakeRepository:
        def ping(self):
            return True

    class HealthDbStockService(FakeStockService):
        repository = FakeRepository()

    monkeypatch.setattr("app.api.routes.get_stock_data_service", lambda: HealthDbStockService())
    client = TestClient(app)

    response = client.get("/health/db")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["backend"] == "sqlite"


def test_health_sources_reports_source_configuration(monkeypatch) -> None:
    monkeypatch.setattr("app.api.routes.settings.tushare_token", None)
    monkeypatch.setattr("app.api.routes.settings.tushare_base_url", "https://api.tushare.pro")
    monkeypatch.setattr("app.api.routes.settings.cninfo_announcements_url", "https://www.cninfo.com.cn/new/hisAnnouncement/query")
    client = TestClient(app)

    response = client.get("/health/sources")

    assert response.status_code == 200
    payload = response.json()
    SourcesHealthResponse.model_validate(payload)
    assert payload["status"] == "ok"
    assert payload["summary"] == {
        "status": "partial",
        "total_sources": 3,
        "configured_count": 2,
        "unconfigured_count": 1,
    }
    assert "tushare" in payload["sources"]
    assert "cninfo" in payload["sources"]
    assert payload["sources"]["tushare"]["configured"] is False
    assert payload["sources"]["tushare"]["base_url"] == "https://api.tushare.pro"
    assert payload["sources"]["cninfo"]["configured"] is True
    assert payload["sources"]["cninfo"]["url"] == "https://www.cninfo.com.cn/new/hisAnnouncement/query"
    assert payload["sources"]["akshare"]["configured"] is True


def test_health_sources_uses_same_top_level_observability_shape_as_sync(monkeypatch) -> None:
    class FakeRepository:
        def list_sync_state(self, ticker: str | None = None):
            return []

    class HealthStockService(FakeStockService):
        repository = FakeRepository()

    monkeypatch.setattr("app.api.routes.settings.tushare_token", "token")
    monkeypatch.setattr("app.api.routes.settings.tushare_base_url", "https://api.tushare.pro")
    monkeypatch.setattr("app.api.routes.settings.cninfo_announcements_url", "https://www.cninfo.com.cn/new/hisAnnouncement/query")
    monkeypatch.setattr("app.api.routes.get_stock_data_service", lambda: HealthStockService())
    client = TestClient(app)

    sources_response = client.get("/health/sources")
    sync_response = client.get("/health/sync")

    assert sources_response.status_code == 200
    assert sync_response.status_code == 200
    sources_payload = sources_response.json()
    sync_payload = sync_response.json()
    assert set(sources_payload) == {"status", "summary", "sources"}
    assert set(sync_payload) == {"status", "ticker", "summary", "items"}
    assert sources_payload["status"] == "ok"
    assert sources_payload["summary"]["status"] == "ok"
    assert sync_payload["status"] == "ok"
    assert "summary" in sources_payload
    assert "summary" in sync_payload
    assert "sources" in sources_payload
    assert "items" in sync_payload


def test_health_sources_keeps_top_level_status_endpoint_oriented_when_configuration_is_partial(monkeypatch) -> None:
    monkeypatch.setattr("app.api.routes.settings.tushare_token", None)
    monkeypatch.setattr("app.api.routes.settings.tushare_base_url", "https://api.tushare.pro")
    monkeypatch.setattr("app.api.routes.settings.cninfo_announcements_url", "https://www.cninfo.com.cn/new/hisAnnouncement/query")
    client = TestClient(app)

    response = client.get("/health/sources")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["summary"]["status"] == "partial"


def test_health_sync_returns_repository_sync_state(monkeypatch) -> None:
    class FakeRepository:
        def list_sync_state(self, ticker: str | None = None):
            return [{
                "dataset": "company_profile",
                "ticker": ticker or "000001.SZ",
                "status": "partial",
                "synced_at": "2026-03-17T00:00:00Z",
                "last_synced_at": "2026-03-17T00:00:00Z",
                "last_success_at": "2026-03-17T00:00:00Z",
                "last_error_at": "2026-03-16T23:59:00Z",
                "last_error_message": "upstream timeout",
                "records_written": 1,
                "duration_ms": 120,
            }]

        def ping(self):
            return True

    class HealthStockService(FakeStockService):
        repository = FakeRepository()

    monkeypatch.setattr("app.api.routes.get_stock_data_service", lambda: HealthStockService())
    client = TestClient(app)

    response = client.get("/health/sync?ticker=000001.SZ")

    assert response.status_code == 200
    payload = response.json()
    SyncHealthResponse.model_validate(payload)
    assert payload["summary"] == {
        "status": "partial",
        "ok_count": 0,
        "partial_count": 1,
        "failed_count": 0,
        "latest_degraded_dataset": "company_profile",
    }
    assert payload["items"][0]["dataset"] == "company_profile"
    assert payload["items"][0]["status"] == "partial"
    assert payload["items"][0]["last_error_at"] == "2026-03-16T23:59:00Z"
    assert payload["items"][0]["last_error_message"] == "upstream timeout"
    assert payload["items"][0]["records_written"] == 1
    assert payload["items"][0]["duration_ms"] == 120


def test_health_sync_normalizes_ticker_filter(monkeypatch) -> None:
    calls = []

    class FakeRepository:
        def list_sync_state(self, ticker: str | None = None):
            calls.append(ticker)
            return [{"dataset": "company_profile", "ticker": ticker, "status": "ok"}]

    class HealthStockService(FakeStockService):
        repository = FakeRepository()

    monkeypatch.setattr("app.api.routes.get_stock_data_service", lambda: HealthStockService())
    client = TestClient(app)

    response = client.get("/health/sync?ticker=000001")

    assert response.status_code == 200
    payload = response.json()
    assert calls == ["000001.SZ"]
    assert payload["ticker"] == "000001.SZ"
    assert payload["summary"]["status"] == "ok"
    assert payload["summary"]["ok_count"] == 1
    assert payload["items"][0]["ticker"] == "000001.SZ"


def test_health_sync_without_ticker_returns_all_rows(monkeypatch) -> None:
    calls = []

    class FakeRepository:
        def list_sync_state(self, ticker: str | None = None):
            calls.append(ticker)
            return [
                {"dataset": "company_profile", "ticker": "000001.SZ", "status": "ok"},
                {"dataset": "company_profile", "ticker": "600519.SH", "status": "ok"},
            ]

    class HealthStockService(FakeStockService):
        repository = FakeRepository()

    monkeypatch.setattr("app.api.routes.get_stock_data_service", lambda: HealthStockService())
    client = TestClient(app)

    response = client.get("/health/sync")

    assert response.status_code == 200
    payload = response.json()
    assert calls == [None]
    assert payload["ticker"] is None
    assert payload["summary"]["status"] == "ok"
    assert payload["summary"]["ok_count"] == 2
    assert len(payload["items"]) == 2


def test_health_sync_preserves_mixed_state_rows_for_normalized_ticker(monkeypatch) -> None:
    calls = []

    class FakeRepository:
        def list_sync_state(self, ticker: str | None = None):
            calls.append(ticker)
            return [
                {
                    "dataset": "company_profile",
                    "ticker": ticker,
                    "status": "ok",
                    "synced_at": "2026-03-17T00:00:00Z",
                    "last_synced_at": "2026-03-17T00:00:00Z",
                    "last_success_at": "2026-03-17T00:00:00Z",
                    "last_error_at": "2026-03-16T23:59:00Z",
                    "last_error_message": "previous timeout",
                    "records_written": 1,
                    "duration_ms": 100,
                },
                {
                    "dataset": "event",
                    "ticker": ticker,
                    "status": "partial",
                    "synced_at": "2026-03-17T00:05:00Z",
                    "last_synced_at": "2026-03-17T00:05:00Z",
                    "last_success_at": "2026-03-17T00:05:00Z",
                    "last_error_at": "2026-03-17T00:05:00Z",
                    "last_error_message": "cninfo timeout",
                    "records_written": 4,
                    "duration_ms": 220,
                },
            ]

    class HealthStockService(FakeStockService):
        repository = FakeRepository()

    monkeypatch.setattr("app.api.routes.get_stock_data_service", lambda: HealthStockService())
    client = TestClient(app)

    response = client.get("/health/sync?ticker=000001")

    assert response.status_code == 200
    payload = response.json()
    assert calls == ["000001.SZ"]
    assert payload["ticker"] == "000001.SZ"
    assert payload["summary"] == {
        "status": "partial",
        "ok_count": 1,
        "partial_count": 1,
        "failed_count": 0,
        "latest_degraded_dataset": "event",
    }
    assert [item["dataset"] for item in payload["items"]] == ["company_profile", "event"]
    assert payload["items"][0]["status"] == "ok"
    assert payload["items"][0]["last_error_message"] == "previous timeout"
    assert payload["items"][1]["status"] == "partial"
    assert payload["items"][1]["last_error_message"] == "cninfo timeout"


def test_health_sync_exposes_mixed_success_and_error_metadata_in_stable_order(monkeypatch) -> None:
    class FakeRepository:
        def list_sync_state(self, ticker: str | None = None):
            return [
                {
                    "dataset": "company_profile",
                    "ticker": "000001.SZ",
                    "status": "ok",
                    "synced_at": "2026-03-17T00:00:00Z",
                    "last_synced_at": "2026-03-17T00:00:00Z",
                    "last_success_at": "2026-03-17T00:00:00Z",
                    "last_error_at": "2026-03-16T23:59:00Z",
                    "last_error_message": "previous timeout",
                    "records_written": 1,
                    "duration_ms": 100,
                },
                {
                    "dataset": "event",
                    "ticker": "000001.SZ",
                    "status": "partial",
                    "synced_at": "2026-03-17T00:05:00Z",
                    "last_synced_at": "2026-03-17T00:05:00Z",
                    "last_success_at": "2026-03-17T00:05:00Z",
                    "last_error_at": "2026-03-17T00:05:00Z",
                    "last_error_message": "cninfo timeout",
                    "records_written": 4,
                    "duration_ms": 220,
                },
                {
                    "dataset": "price_daily",
                    "ticker": "000001.SZ",
                    "status": "ok",
                    "synced_at": "2026-03-17T00:10:00Z",
                    "last_synced_at": "2026-03-17T00:10:00Z",
                    "last_success_at": "2026-03-17T00:10:00Z",
                    "last_error_at": None,
                    "last_error_message": None,
                    "records_written": 60,
                    "duration_ms": 80,
                },
            ]

    class HealthStockService(FakeStockService):
        repository = FakeRepository()

    monkeypatch.setattr("app.api.routes.get_stock_data_service", lambda: HealthStockService())
    client = TestClient(app)

    response = client.get("/health/sync?ticker=000001.SZ")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"] == {
        "status": "partial",
        "ok_count": 2,
        "partial_count": 1,
        "failed_count": 0,
        "latest_degraded_dataset": "event",
    }
    assert [item["dataset"] for item in payload["items"]] == ["company_profile", "event", "price_daily"]
    assert payload["items"][0]["status"] == "ok"
    assert payload["items"][0]["last_error_message"] == "previous timeout"
    assert payload["items"][1]["status"] == "partial"
    assert payload["items"][1]["records_written"] == 4
    assert payload["items"][2]["status"] == "ok"
    assert payload["items"][2]["last_error_message"] is None


def test_health_sync_summary_prefers_failed_and_latest_degraded_dataset(monkeypatch) -> None:
    class FakeRepository:
        def list_sync_state(self, ticker: str | None = None):
            return [
                {
                    "dataset": "company_profile",
                    "ticker": "000001.SZ",
                    "status": "ok",
                    "synced_at": "2026-03-17T00:00:00Z",
                    "last_synced_at": "2026-03-17T00:00:00Z",
                    "last_success_at": "2026-03-17T00:00:00Z",
                    "last_error_at": "2026-03-16T23:59:00Z",
                    "last_error_message": "previous timeout",
                    "records_written": 1,
                    "duration_ms": 100,
                },
                {
                    "dataset": "event",
                    "ticker": "000001.SZ",
                    "status": "partial",
                    "synced_at": "2026-03-17T00:05:00Z",
                    "last_synced_at": "2026-03-17T00:05:00Z",
                    "last_success_at": "2026-03-17T00:05:00Z",
                    "last_error_at": "2026-03-17T00:05:00Z",
                    "last_error_message": "cninfo timeout",
                    "records_written": 4,
                    "duration_ms": 220,
                },
                {
                    "dataset": "financial_summary",
                    "ticker": "000001.SZ",
                    "status": "failed",
                    "synced_at": "2026-03-17T00:10:00Z",
                    "last_synced_at": "2026-03-17T00:10:00Z",
                    "last_success_at": "2026-03-16T00:00:00Z",
                    "last_error_at": "2026-03-17T00:10:00Z",
                    "last_error_message": "upstream unavailable",
                    "records_written": 0,
                    "duration_ms": 350,
                },
            ]

    class HealthStockService(FakeStockService):
        repository = FakeRepository()

    monkeypatch.setattr("app.api.routes.get_stock_data_service", lambda: HealthStockService())
    client = TestClient(app)

    response = client.get("/health/sync?ticker=000001.SZ")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"] == {
        "status": "failed",
        "ok_count": 1,
        "partial_count": 1,
        "failed_count": 1,
        "latest_degraded_dataset": "financial_summary",
    }
    assert [item["dataset"] for item in payload["items"]] == ["company_profile", "event", "financial_summary"]
