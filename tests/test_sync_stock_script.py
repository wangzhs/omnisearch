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
            self.data_status = type("Status", (), {"status": "fresh", "last_error_message": None, "error_message": None})()
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
                    "data_status": type("Status", (), {"status": "fresh", "last_error_message": None, "error_message": None})(),
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
            assert ticker == "000001.SZ"
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
    assert payload["results"][0]["ticker"] == "000001.SZ"
    assert dataset_status["company"] == "skipped"
    assert dataset_status["overview"] == "ok"
    assert payload["results"][0]["summary"]["skipped_dataset_count"] == 4


def test_sync_stock_script_retries_failures(monkeypatch, capsys) -> None:
    attempts = {"company": 0}

    class FakePriceDebug:
        items = []
        data_status = type("Status", (), {"status": "fresh", "last_error_message": None, "error_message": None})()
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
            return type("EventDebug", (), {"items": [], "data_status": type("Status", (), {"status": "fresh", "last_error_message": None, "error_message": None})(), "debug": []})()

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
            return type("PriceDebug", (), {"items": [], "data_status": type("Status", (), {"status": "fresh", "last_error_message": None, "error_message": None})(), "debug": []})()

        def list_events_with_debug(self, ticker: str, limit: int = 10, refresh: bool = False):
            return type("EventDebug", (), {"items": [], "data_status": type("Status", (), {"status": "fresh", "last_error_message": None, "error_message": None})(), "debug": []})()

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
    assert "[sync] ticker=000001.SZ dataset=company" in captured.err
    assert payload["results"][0]["ticker"] == "000001.SZ"


def test_sync_stock_script_uses_normalized_ticker_for_results_and_sync_state(monkeypatch, capsys) -> None:
    recorded = []

    class FakeRepository:
        def get_last_synced_at(self, dataset: str, ticker: str):
            recorded.append(("read", dataset, ticker))
            return None

        def record_sync_result(self, dataset, ticker, synced_at, **kwargs):
            recorded.append(("write", dataset, ticker, kwargs))

    class FakeService:
        repository = FakeRepository()

        def get_company(self, ticker: str, refresh: bool = False):
            assert ticker == "000001.SZ"
            return type("Company", (), {"name": "Ping An Bank", "source": "tushare"})()

        def list_financials(self, ticker: str, limit: int = 4, refresh: bool = False):
            assert ticker == "000001.SZ"
            return []

        def list_prices_with_debug(self, ticker: str, limit: int = 60, refresh: bool = False):
            assert ticker == "000001.SZ"
            return type("PriceDebug", (), {"items": [], "data_status": type("Status", (), {"status": "fresh", "last_error_message": None, "error_message": None})(), "debug": []})()

        def list_events_with_debug(self, ticker: str, limit: int = 10, refresh: bool = False):
            assert ticker == "000001.SZ"
            return type("EventDebug", (), {"items": [], "data_status": type("Status", (), {"status": "fresh", "last_error_message": None, "error_message": None})(), "debug": []})()

        def get_overview(self, ticker: str, refresh: bool = False):
            assert ticker == "000001.SZ"
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
    monkeypatch.setattr("sys.argv", ["sync_stock.py", "--tickers", "000001", "--incremental"])

    sync_stock.main()

    payload = json.loads(capsys.readouterr().out)
    assert payload["results"][0]["ticker"] == "000001.SZ"
    assert all(entry[2] == "000001.SZ" for entry in recorded if entry[0] in {"read", "write"})


def test_sync_stock_script_preserves_partial_sync_observability(monkeypatch, capsys) -> None:
    recorded = []

    class FakeRepository:
        def get_last_synced_at(self, dataset: str, ticker: str):
            return None

        def record_sync_result(self, dataset, ticker, synced_at, **kwargs):
            recorded.append({"dataset": dataset, "ticker": ticker, **kwargs})

    class FakeService:
        repository = FakeRepository()

        def get_company(self, ticker: str, refresh: bool = False):
            return type("Company", (), {"name": "Ping An Bank", "source": "tushare"})()

        def list_financials(self, ticker: str, limit: int = 4, refresh: bool = False):
            return []

        def list_prices_with_debug(self, ticker: str, limit: int = 60, refresh: bool = False):
            return type(
                "PriceDebug",
                (),
                {
                    "items": [1],
                    "data_status": type("Status", (), {"status": "partial", "last_error_message": "tushare timeout", "error_message": "tushare timeout"})(),
                    "debug": [],
                },
            )()

        def list_events_with_debug(self, ticker: str, limit: int = 10, refresh: bool = False):
            return type(
                "EventDebug",
                (),
                {
                    "items": [1],
                    "data_status": type("Status", (), {"status": "partial", "last_error_message": "cninfo timeout", "error_message": "cninfo timeout"})(),
                    "debug": [],
                },
            )()

        def get_overview(self, ticker: str, refresh: bool = False):
            raise AssertionError("overview should be skipped")

    monkeypatch.setattr("app.scripts.sync_stock.get_stock_data_service", lambda: FakeService())
    monkeypatch.setattr("sys.argv", ["sync_stock.py", "--tickers", "000001", "--skip-overview"])

    sync_stock.main()

    payload = json.loads(capsys.readouterr().out)
    assert payload["results"][0]["price_count"] == 1
    assert payload["results"][0]["event_count"] == 1
    price_record = next(item for item in recorded if item["dataset"] == "price_daily")
    event_record = next(item for item in recorded if item["dataset"] == "event")
    assert price_record["success"] is True
    assert price_record["error_message"] == "tushare timeout"
    assert event_record["success"] is True
    assert event_record["error_message"] == "cninfo timeout"


def test_sync_stock_script_reports_mixed_outcomes_stably(monkeypatch, capsys) -> None:
    class FakeRepository:
        def get_last_synced_at(self, dataset: str, ticker: str):
            if dataset == "company_profile":
                return "2099-03-17T00:00:00Z"
            return None

    class FakeService:
        repository = FakeRepository()

        def list_financials(self, ticker: str, limit: int = 4, refresh: bool = False):
            raise RuntimeError("financial source down")

        def list_prices_with_debug(self, ticker: str, limit: int = 60, refresh: bool = False):
            return type(
                "PriceDebug",
                (),
                {
                    "items": [1],
                    "data_status": type("Status", (), {"status": "partial", "last_error_message": "tushare timeout", "error_message": "tushare timeout"})(),
                    "debug": [],
                },
            )()

        def list_events_with_debug(self, ticker: str, limit: int = 10, refresh: bool = False):
            return type(
                "EventDebug",
                (),
                {
                    "items": [1, 2],
                    "data_status": type("Status", (), {"status": "fresh", "last_error_message": None, "error_message": None})(),
                    "debug": [],
                },
            )()

        def get_overview(self, ticker: str, refresh: bool = False):
            return type(
                "Overview",
                (),
                {
                    "company": type("Section", (), {"data": None, "data_status": type("Status", (), {"status": "fresh", "model_dump": lambda self: {"status": "fresh"}})()})(),
                    "latest_financial": type("Section", (), {"data": None, "data_status": type("Status", (), {"status": "partial", "model_dump": lambda self: {"status": "partial"}})()})(),
                    "latest_price": type("Section", (), {"data": None, "data_status": type("Status", (), {"status": "partial", "model_dump": lambda self: {"status": "partial"}})()})(),
                    "recent_events": type("Section", (), {"data_status": type("Status", (), {"status": "fresh", "model_dump": lambda self: {"status": "fresh"}})()})(),
                    "risk_flags": type("Section", (), {"data": [1], "data_status": type("Status", (), {"status": "partial", "model_dump": lambda self: {"status": "partial"}})()})(),
                    "signals": type("Section", (), {"data": [], "data_status": type("Status", (), {"status": "partial", "model_dump": lambda self: {"status": "partial"}})()})(),
                },
            )()

    monkeypatch.setattr("app.scripts.sync_stock.get_stock_data_service", lambda: FakeService())
    monkeypatch.setattr(
        "sys.argv",
        ["sync_stock.py", "--tickers", "000001", "--incremental", "--skip-company"],
    )

    sync_stock.main()

    payload = json.loads(capsys.readouterr().out)
    result = payload["results"][0]
    dataset_status = {item["dataset"]: item["status"] for item in result["datasets"]}

    assert result["status"] == "partial"
    assert result["summary"]["planned_dataset_count"] == 4
    assert result["summary"]["ok_dataset_count"] == 1
    assert result["summary"]["partial_dataset_count"] == 2
    assert result["summary"]["failed_dataset_count"] == 1
    assert result["summary"]["skipped_dataset_count"] == 0
    assert dataset_status == {
        "financials": "failed",
        "prices": "partial",
        "events": "ok",
        "overview": "partial",
    }
    assert result["overview"]["section_status"]["latest_financial"]["status"] == "partial"
    assert result["overview"]["section_status"]["signals"]["status"] == "partial"
    assert payload["summary"]["ticker_count"] == 1
    assert payload["summary"]["partial_ticker_count"] == 1
    assert payload["summary"]["ok_ticker_count"] == 0
    assert payload["failure_count"] == 1
    assert payload["failures"][0]["errors"]["financial_error"] == "financial source down"
