import json

from app.scripts import sync_stock


def test_sync_stock_script_outputs_summary(monkeypatch, capsys) -> None:
    class FakePriceDebug:
        def __init__(self):
            self.items = [object(), object()]
            self.debug = [type("Debug", (), {"model_dump": lambda self: {"source": "akshare", "status": "ok", "count": 2, "error": None}})()]

    class FakeCompany:
        name = "Ping An Bank"

    class FakeService:
        def get_company(self, ticker: str, refresh: bool = False):
            return FakeCompany()

        def list_financials(self, ticker: str, limit: int = 4, refresh: bool = False):
            return [1, 2, 3]

        def list_prices_with_debug(self, ticker: str, limit: int = 60, refresh: bool = False):
            return FakePriceDebug()

        def list_events(self, ticker: str, limit: int = 10, refresh: bool = False):
            return [1]

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
