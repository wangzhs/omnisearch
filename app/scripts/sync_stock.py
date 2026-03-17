import argparse
import json

from app.services.stock import get_stock_data_service


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync and warm stock datasets into local SQLite.")
    parser.add_argument("--tickers", required=True, help="Comma-separated tickers, e.g. 000001,002837")
    parser.add_argument("--refresh", action="store_true", help="Force refresh upstream data")
    parser.add_argument("--price-limit", type=int, default=60, help="Number of daily price rows to warm")
    args = parser.parse_args()

    service = get_stock_data_service()
    tickers = [item.strip() for item in args.tickers.split(",") if item.strip()]
    results: list[dict] = []

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
            events = service.list_events(ticker, limit=10, refresh=args.refresh)
            result["event_count"] = len(events)
        except Exception as exc:
            result["event_error"] = str(exc)

        if any(key.endswith("_error") for key in result):
            result["status"] = "partial"
        results.append(result)

    print(json.dumps({"results": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
