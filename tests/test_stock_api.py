from fastapi.testclient import TestClient

from app.main import app
from app.normalizers.stock import normalize_price_daily
from app.schemas.search import SearchResult


class FakeStockService:
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
            "updated_at": "2026-03-17T00:00:00Z",
            "raw": {},
        }

    def list_events(self, ticker: str, limit: int = 20, refresh: bool = False):
        return [
            {
                "event_id": "evt-1",
                "ticker": "000001.SZ",
                "event_date": "2026-03-16",
                "title": "Annual report disclosed",
                "category": "report",
                "source": "cninfo",
                "url": "https://example.com/report.pdf",
                "summary": "Annual report filing",
                "updated_at": "2026-03-17T00:00:00Z",
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
                "updated_at": "2026-03-17T00:00:00Z",
                "raw": {},
            }
        ]

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
                "raw": {},
            }
        ]

    def get_overview(self, ticker: str, refresh: bool = False):
        return {
            "company": self.get_company(ticker, refresh=refresh),
            "latest_financial": self.list_financials(ticker, refresh=refresh)[0],
            "latest_price": self.list_prices(ticker, refresh=refresh)[0],
            "recent_events": self.list_events(ticker, refresh=refresh),
            "risk_flags": self.get_risk_flags(ticker, refresh=refresh),
            "data_status": [
                {"dataset": "company", "status": "ok", "source": "tushare", "count": 1, "as_of_date": "2026-03-17T00:00:00Z", "message": None},
                {"dataset": "financials", "status": "ok", "source": "tushare", "count": 1, "as_of_date": "2026-03-16", "message": None},
                {"dataset": "prices", "status": "ok", "source": "akshare", "count": 1, "as_of_date": "2026-03-13", "message": None},
                {"dataset": "events", "status": "ok", "source": "cninfo", "count": 1, "as_of_date": "2026-03-16", "message": None},
            ],
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
        overview = self.get_overview(ticker, refresh=refresh)
        return {"ticker": "000001.SZ", **overview}


def test_company_overview_endpoint_returns_stock_snapshot(monkeypatch) -> None:
    monkeypatch.setattr("app.api.routes.get_stock_data_service", lambda: FakeStockService())

    client = TestClient(app)
    response = client.get("/company/000001/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["company"]["ticker"] == "000001.SZ"
    assert payload["latest_financial"]["net_profit"] == -5.0
    assert payload["risk_flags"][0]["code"] == "negative_net_profit"
    assert payload["data_status"][0]["dataset"] == "company"
    assert payload["data_status"][1]["dataset"] == "financials"
    assert "raw" not in payload["company"]
    assert "raw" not in payload["latest_financial"]
    assert "raw" not in payload["latest_price"]


def test_company_overview_falls_back_when_company_profile_missing(monkeypatch) -> None:
    class PartialStockService(FakeStockService):
        def get_overview(self, ticker: str, refresh: bool = False):
            return {
                "company": {
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
                "latest_financial": self.list_financials(ticker, refresh=refresh)[0],
                "latest_price": self.list_prices(ticker, refresh=refresh)[0],
                "recent_events": self.list_events(ticker, refresh=refresh),
                "risk_flags": self.get_risk_flags(ticker, refresh=refresh),
                "data_status": [
                    {"dataset": "company", "status": "partial", "source": "fallback", "count": 0, "as_of_date": None, "message": "Using fallback company profile."}
                ],
            }

    monkeypatch.setattr("app.api.routes.get_stock_data_service", lambda: PartialStockService())

    client = TestClient(app)
    response = client.get("/company/002837/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["company"]["ticker"] == "002837.SZ"
    assert payload["company"]["source"] == "fallback"


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
                        "ticker": ticker,
                        "event_date": None,
                        "title": "英维克 关于年报的公告",
                        "category": "exchange_disclosure",
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
                "debug": [
                    {"source": "akshare", "status": "error", "count": 0, "error": "empty reply"},
                    {"source": "tushare", "status": "empty", "count": 0, "error": None},
                ],
            }

    monkeypatch.setattr("app.api.routes.get_stock_data_service", lambda: DebugStockService())

    client = TestClient(app)
    response = client.get("/company/002837/prices?debug=true")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "002837.SZ"
    assert payload["debug"][0]["source"] == "akshare"
    assert payload["debug"][1]["status"] == "empty"


def test_events_debug_endpoint_returns_source_status(monkeypatch) -> None:
    class DebugStockService(FakeStockService):
        def list_events_with_debug(self, ticker: str, limit: int = 20, refresh: bool = False):
            return {
                "ticker": "002837.SZ",
                "items": [],
                "debug": [
                    {"source": "cninfo", "status": "empty", "count": 0, "kept_count": 0, "error": None},
                    {"source": "exchange_search", "status": "ok", "count": 12, "kept_count": 4, "error": None},
                ],
            }

    monkeypatch.setattr("app.api.routes.get_stock_data_service", lambda: DebugStockService())

    client = TestClient(app)
    response = client.get("/company/002837/events?debug=true")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "002837.SZ"
    assert payload["debug"][0]["source"] == "cninfo"
    assert payload["debug"][1]["kept_count"] == 4
