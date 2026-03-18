import argparse
import json

from app.services.stock import get_stock_data_service


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync and warm stock datasets into local SQLite.")
    parser.add_argument("--tickers", required=True, help="Comma-separated tickers, e.g. 000001,002837")
    parser.add_argument("--refresh", action="store_true", help="Force refresh upstream data")
    parser.add_argument("--price-limit", type=int, default=60, help="Number of daily price rows to warm")
    parser.add_argument("--event-limit", type=int, default=10, help="Number of event rows to warm")
    args = parser.parse_args()

    service = get_stock_data_service()
    tickers = [item.strip() for item in args.tickers.split(",") if item.strip()]
    results: list[dict] = []
    failures: list[dict] = []

    for ticker in tickers:
        result: dict = {"ticker": ticker, "status": "ok"}
        try:
            company = service.get_company(ticker, refresh=args.refresh)
            result["company_name"] = company.name
        except Exception as exc:
            result["company_error"] = str(exc)

        try:
            financials = service.list_financials(ticker, limit=4, refresh=args.refresh)
            result["financial_count"] = len(financials)
        except Exception as exc:
            result["financial_error"] = str(exc)

        try:
            prices_debug = service.list_prices_with_debug(
                ticker,
                limit=args.price_limit,
                refresh=args.refresh,
            )
            result["price_count"] = len(prices_debug.items)
            result["price_debug"] = [item.model_dump() for item in prices_debug.debug]
        except Exception as exc:
            result["price_error"] = str(exc)

        try:
            events_debug = service.list_events_with_debug(ticker, limit=args.event_limit, refresh=args.refresh)
            result["event_count"] = len(events_debug.items)
            result["event_debug"] = [item.model_dump() for item in events_debug.debug]
        except Exception as exc:
            result["event_error"] = str(exc)

        try:
            overview = service.get_overview(ticker, refresh=False)
            result["overview"] = {
                "company_name": overview.company.name,
                "latest_financial_date": overview.latest_financial.report_date if overview.latest_financial else None,
                "latest_price_date": overview.latest_price.trade_date if overview.latest_price else None,
                "risk_flag_count": len(overview.risk_flags),
                "data_status": [item.model_dump() for item in overview.data_status],
            }
        except Exception as exc:
            result["overview_error"] = str(exc)

        if any(key.endswith("_error") for key in result):
            result["status"] = "partial"
            failures.append(
                {
                    "ticker": ticker,
                    "errors": {key: value for key, value in result.items() if key.endswith("_error")},
                }
            )
        results.append(result)

    print(json.dumps({"results": results, "failure_count": len(failures), "failures": failures}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
