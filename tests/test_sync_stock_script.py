import json
from pathlib import Path

from app.scripts import sync_stock


def test_sync_stock_script_outputs_summary(monkeypatch, capsys) -> None:
    recorded = []

    class FakeRepository:
        def record_sync_result(self, dataset, ticker, synced_at, **kwargs):
            recorded.append({"dataset": dataset, "ticker": ticker, "synced_at": synced_at, **kwargs})

    class FakePriceDebug:
        def __init__(self):
            self.items = [object(), object()]
            self.debug = [type("Debug", (), {"model_dump": lambda self: {"source": "akshare", "status": "ok", "count": 2, "error": None}})()]

    class FakeCompany:
        name = "Ping An Bank"
        source = "tushare"

    class FakeService:
        repository = FakeRepository()

        def get_company(self, ticker: str, refresh: bool = False):
            return FakeCompany()

        def list_financials(self, ticker: str, limit: int = 4, refresh: bool = False):
            return [1, 2, 3]

        def list_prices_with_debug(self, ticker: str, limit: int = 60, refresh: bool = False):
            return FakePriceDebug()

        def list_events_with_debug(self, ticker: str, limit: int = 10, refresh: bool = False):
            return type(
                "EventDebug",
                (),
                {
                    "items": [1],
                    "debug": [type("Debug", (), {"model_dump": lambda self: {"source": "exchange_search", "status": "ok", "count": 2, "kept_count": 1, "error": None}})()],
                },
            )()

        def get_overview(self, ticker: str, refresh: bool = False):
            return type(
                "Overview",
                (),
                {
                    "company": type(
                        "Section",
                        (),
                        {
                            "data": type("Company", (), {"name": "Ping An Bank"})(),
                            "data_status": type("Status", (), {"model_dump": lambda self: {"status": "fresh"}})(),
                        },
                    )(),
                    "latest_financial": type(
                        "Section",
                        (),
                        {
                            "data": type("Financial", (), {"report_date": "2025-12-31"})(),
                            "data_status": type("Status", (), {"model_dump": lambda self: {"status": "fresh"}})(),
                        },
                    )(),
                    "latest_price": type(
                        "Section",
                        (),
                        {
                            "data": type("Price", (), {"trade_date": "2026-03-17"})(),
                            "data_status": type("Status", (), {"model_dump": lambda self: {"status": "fresh"}})(),
                        },
                    )(),
                    "recent_events": type(
                        "Section",
                        (),
                        {"data_status": type("Status", (), {"model_dump": lambda self: {"status": "fresh"}})()},
                    )(),
                    "risk_flags": type(
                        "Section",
                        (),
                        {
                            "data": [1, 2],
                            "data_status": type("Status", (), {"model_dump": lambda self: {"status": "fresh"}})(),
                        },
                    )(),
                    "signals": type(
                        "Section",
                        (),
                        {
                            "data": [],
                            "data_status": type("Status", (), {"model_dump": lambda self: {"status": "fresh"}})(),
                        },
                    )(),
                },
            )()

    monkeypatch.setattr("app.scripts.sync_stock.get_stock_data_service", lambda: FakeService())
    monkeypatch.setattr(
        "sys.argv",
        ["sync_stock.py", "--tickers", "000001,002837", "--refresh"],
    )

    sync_stock.main()

    payload = json.loads(capsys.readouterr().out)
    assert len(payload["results"]) == 2
    assert payload["results"][0]["company_name"] == "Ping An Bank"
    assert payload["results"][0]["price_count"] == 2
    assert payload["results"][0]["event_count"] == 1
    assert payload["results"][0]["overview"]["risk_flag_count"] == 2
    assert payload["results"][0]["overview"]["section_status"]["signals"]["status"] == "fresh"
    assert payload["results"][0]["datasets"][0]["dataset"] == "company"
    assert payload["results"][0]["summary"]["ok_dataset_count"] == 5
    assert payload["summary"]["ticker_count"] == 2
    assert payload["failure_count"] == 0
    assert any(item["dataset"] == "overview" for item in recorded)
    assert all(item["duration_ms"] is not None for item in recorded)


def test_sync_stock_script_supports_dry_run(monkeypatch, capsys) -> None:
    monkeypatch.setattr("app.scripts.sync_stock.get_stock_data_service", lambda: object())
    monkeypatch.setattr(
        "sys.argv",
        ["sync_stock.py", "--tickers", "000001", "--dry-run", "--skip-overview"],
    )

    sync_stock.main()

    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "dry_run"
    assert payload["results"][0]["status"] == "dry_run"
    assert payload["results"][0]["summary"]["planned_dataset_count"] == 4
    assert payload["selected_datasets"] == ["company", "financials", "prices", "events"]


def test_sync_stock_script_skips_fresh_datasets_in_incremental_mode(monkeypatch, capsys) -> None:
    class FakeRepository:
        def get_last_synced_at(self, dataset: str, ticker: str):
            return "2099-03-17T00:00:00Z"

    class FakeService:
        repository = FakeRepository()

        def get_overview(self, ticker: str, refresh: bool = False):
            return type(
                "Overview",
                (),
                {
                    "company": type("Section", (), {"data": None, "data_status": type("Status", (), {"model_dump": lambda self: {"status": "fresh"}})()})(),
                    "latest_financial": type("Section", (), {"data": None, "data_status": type("Status", (), {"model_dump": lambda self: {"status": "fresh"}})()})(),
                    "latest_price": type("Section", (), {"data": None, "data_status": type("Status", (), {"model_dump": lambda self: {"status": "fresh"}})()})(),
                    "recent_events": type("Section", (), {"data_status": type("Status", (), {"model_dump": lambda self: {"status": "fresh"}})()})(),
                    "risk_flags": type("Section", (), {"data": [], "data_status": type("Status", (), {"model_dump": lambda self: {"status": "fresh"}})()})(),
                    "signals": type("Section", (), {"data": [], "data_status": type("Status", (), {"model_dump": lambda self: {"status": "fresh"}})()})(),
                },
            )()

    monkeypatch.setattr("app.scripts.sync_stock.get_stock_data_service", lambda: FakeService())
    monkeypatch.setattr(
        "sys.argv",
        ["sync_stock.py", "--tickers", "000001", "--incremental"],
    )

    sync_stock.main()

    payload = json.loads(capsys.readouterr().out)
    dataset_status = {item["dataset"]: item["status"] for item in payload["results"][0]["datasets"]}
    assert dataset_status["company"] == "skipped"
    assert dataset_status["overview"] == "ok"
    assert payload["results"][0]["summary"]["skipped_dataset_count"] == 4


def test_sync_stock_script_retries_failures(monkeypatch, capsys) -> None:
    attempts = {"company": 0}

    class FakePriceDebug:
        items = []
        debug = []

    class FakeService:
        repository = type("Repo", (), {"get_last_synced_at": lambda self, dataset, ticker: None})()

        def get_company(self, ticker: str, refresh: bool = False):
            attempts["company"] += 1
            if attempts["company"] == 1:
                raise RuntimeError("temporary failure")
            return type("Company", (), {"name": "Ping An Bank", "source": "tushare"})()

        def list_financials(self, ticker: str, limit: int = 4, refresh: bool = False):
            return []

        def list_prices_with_debug(self, ticker: str, limit: int = 60, refresh: bool = False):
            return FakePriceDebug()

        def list_events_with_debug(self, ticker: str, limit: int = 10, refresh: bool = False):
            return type("EventDebug", (), {"items": [], "debug": []})()

        def get_overview(self, ticker: str, refresh: bool = False):
            return type(
                "Overview",
                (),
                {
                    "company": type("Section", (), {"data": None, "data_status": type("Status", (), {"model_dump": lambda self: {"status": "fresh"}})()})(),
                    "latest_financial": type("Section", (), {"data": None, "data_status": type("Status", (), {"model_dump": lambda self: {"status": "fresh"}})()})(),
                    "latest_price": type("Section", (), {"data": None, "data_status": type("Status", (), {"model_dump": lambda self: {"status": "fresh"}})()})(),
                    "recent_events": type("Section", (), {"data_status": type("Status", (), {"model_dump": lambda self: {"status": "fresh"}})()})(),
                    "risk_flags": type("Section", (), {"data": [], "data_status": type("Status", (), {"model_dump": lambda self: {"status": "fresh"}})()})(),
                    "signals": type("Section", (), {"data": [], "data_status": type("Status", (), {"model_dump": lambda self: {"status": "fresh"}})()})(),
                },
            )()

    monkeypatch.setattr("app.scripts.sync_stock.get_stock_data_service", lambda: FakeService())
    monkeypatch.setattr("app.scripts.sync_stock.time.sleep", lambda seconds: None)
    monkeypatch.setattr(
        "sys.argv",
        ["sync_stock.py", "--tickers", "000001", "--retries", "1", "--skip-overview"],
    )

    sync_stock.main()

    payload = json.loads(capsys.readouterr().out)
    assert attempts["company"] == 2
    assert payload["results"][0]["status"] == "ok"
    assert payload["results"][0]["summary"]["ok_dataset_count"] == 4


def test_sync_stock_script_writes_json_report_and_verbose_logs(monkeypatch, capsys, tmp_path: Path) -> None:
    report_path = tmp_path / "sync-report.json"

    class FakeService:
        repository = type("Repo", (), {"get_last_synced_at": lambda self, dataset, ticker: None})()

        def get_company(self, ticker: str, refresh: bool = False):
            return type("Company", (), {"name": "Ping An Bank", "source": "tushare"})()

        def list_financials(self, ticker: str, limit: int = 4, refresh: bool = False):
            return []

        def list_prices_with_debug(self, ticker: str, limit: int = 60, refresh: bool = False):
            return type("PriceDebug", (), {"items": [], "debug": []})()

        def list_events_with_debug(self, ticker: str, limit: int = 10, refresh: bool = False):
            return type("EventDebug", (), {"items": [], "debug": []})()

        def get_overview(self, ticker: str, refresh: bool = False):
            return type(
                "Overview",
                (),
                {
                    "company": type("Section", (), {"data": None, "data_status": type("Status", (), {"model_dump": lambda self: {"status": "fresh"}})()})(),
                    "latest_financial": type("Section", (), {"data": None, "data_status": type("Status", (), {"model_dump": lambda self: {"status": "fresh"}})()})(),
                    "latest_price": type("Section", (), {"data": None, "data_status": type("Status", (), {"model_dump": lambda self: {"status": "fresh"}})()})(),
                    "recent_events": type("Section", (), {"data_status": type("Status", (), {"model_dump": lambda self: {"status": "fresh"}})()})(),
                    "risk_flags": type("Section", (), {"data": [], "data_status": type("Status", (), {"model_dump": lambda self: {"status": "fresh"}})()})(),
                    "signals": type("Section", (), {"data": [], "data_status": type("Status", (), {"model_dump": lambda self: {"status": "fresh"}})()})(),
                },
            )()

    monkeypatch.setattr("app.scripts.sync_stock.get_stock_data_service", lambda: FakeService())
    monkeypatch.setattr(
        "sys.argv",
        ["sync_stock.py", "--tickers", "000001", "--verbose", "--json-report", str(report_path)],
    )

    sync_stock.main()

    captured = capsys.readouterr()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert "[sync] ticker=000001 dataset=company" in captured.err
    assert payload["results"][0]["ticker"] == "000001"
