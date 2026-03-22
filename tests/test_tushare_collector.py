from app.collectors.tushare import TushareCollector


def test_tushare_collector_merges_income_and_indicator_rows(monkeypatch) -> None:
    collector = TushareCollector()

    def fake_get_client():
        return object()

    def fake_call_api(client, api_name: str, params, fields: str):
        if api_name == "income":
            return [
                {
                    "end_date": "20251231",
                    "ann_date": "20260316",
                    "report_type": "annual",
                    "total_revenue": 100.0,
                    "n_income": 10.0,
                    "basic_eps": 0.2,
                }
            ]
        if api_name == "fina_indicator":
            return [
                {
                    "end_date": "20251231",
                    "q_sales_yoy": 3.0,
                    "q_dtprofit_yoy": 4.0,
                    "roe": 1.5,
                    "grossprofit_margin": 30.0,
                }
            ]
        raise AssertionError(api_name)

    monkeypatch.setattr(collector, "_get_client", fake_get_client)
    monkeypatch.setattr(collector, "_call_api", fake_call_api)

    items = collector.fetch_financial_summaries("000001", limit=1)

    assert len(items) == 1
    assert items[0]["total_revenue"] == 100.0
    assert items[0]["q_sales_yoy"] == 3.0
    assert items[0]["grossprofit_margin"] == 30.0
