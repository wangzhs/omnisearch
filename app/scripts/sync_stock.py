import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from app.core.config import settings
from app.services.stock import get_stock_data_service

DATASETS = ("company", "financials", "prices", "events", "overview")
SYNC_STATE_DATASET = {
    "company": "company_profile",
    "financials": "financial_summary",
    "prices": "price_daily",
    "events": "event",
    "overview": None,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync and warm A-share stock datasets into local SQLite.")
    parser.add_argument("--tickers", required=True, help="Comma-separated tickers, e.g. 000001,002837")
    parser.add_argument("--refresh", action="store_true", help="Force refresh upstream data")
    parser.add_argument("--incremental", action="store_true", help="Skip datasets that are still fresh per local sync state")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be synced without calling upstream collectors")
    parser.add_argument("--verbose", action="store_true", help="Print progress logs to stderr")
    parser.add_argument("--json-report", help="Optional path to write the final JSON report")
    parser.add_argument("--price-limit", type=int, default=60, help="Number of daily price rows to warm")
    parser.add_argument("--event-limit", type=int, default=10, help="Number of event rows to warm")
    parser.add_argument("--retries", type=int, default=2, help="Retries per dataset after the first attempt fails")
    parser.add_argument("--retry-backoff-seconds", type=float, default=1.0, help="Base backoff seconds between retries")
    parser.add_argument("--skip-company", action="store_true", help="Skip company profile sync")
    parser.add_argument("--skip-financials", action="store_true", help="Skip financial summary sync")
    parser.add_argument("--skip-prices", action="store_true", help="Skip daily price sync")
    parser.add_argument("--skip-events", action="store_true", help="Skip event sync")
    parser.add_argument("--skip-overview", action="store_true", help="Skip overview assembly")
    return parser.parse_args()


def _log(verbose: bool, message: str) -> None:
    if verbose:
        print(message, file=sys.stderr)


def _parse_tickers(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _should_sync_incrementally(service: Any, dataset: str, ticker: str) -> bool:
    sync_dataset = SYNC_STATE_DATASET[dataset]
    if sync_dataset is None:
        return True
    last_synced_at = service.repository.get_last_synced_at(sync_dataset, ticker)
    if not last_synced_at:
        return True
    try:
        synced_at = datetime.fromisoformat(last_synced_at.replace("Z", "+00:00"))
    except ValueError:
        return True
    return synced_at + timedelta(hours=settings.stock_data_ttl_hours) <= datetime.now(timezone.utc)


def _retry_call(
    label: str,
    fn: Callable[[], Any],
    retries: int,
    backoff_seconds: float,
    verbose: bool,
) -> Any:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return fn()
        except Exception as exc:
            last_error = exc
            if attempt >= retries:
                break
            delay = backoff_seconds * (2**attempt)
            _log(verbose, f"[retry] {label} attempt={attempt + 1} failed: {exc}; sleeping {delay:.1f}s")
            time.sleep(delay)
    assert last_error is not None
    raise last_error


def _selected_datasets(args: argparse.Namespace) -> list[str]:
    selected = []
    for dataset in DATASETS:
        if getattr(args, f"skip_{dataset}"):
            continue
        selected.append(dataset)
    return selected


def _dry_run_result(ticker: str, datasets: list[str], incremental: bool) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "status": "dry_run",
        "mode": "incremental" if incremental else "full",
        "summary": {
            "planned_dataset_count": len(datasets),
            "ok_dataset_count": 0,
            "failed_dataset_count": 0,
            "skipped_dataset_count": 0,
        },
        "datasets": [{"dataset": dataset, "status": "planned"} for dataset in datasets],
    }


def _sync_ticker(service: Any, ticker: str, args: argparse.Namespace, datasets: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ticker": ticker,
        "status": "ok",
        "mode": "incremental" if args.incremental else "full",
        "summary": {
            "planned_dataset_count": len(datasets),
            "ok_dataset_count": 0,
            "failed_dataset_count": 0,
            "skipped_dataset_count": 0,
        },
        "datasets": [],
    }
    errors: dict[str, str] = {}

    def record_dataset(dataset: str, status: str, **extra: Any) -> None:
        result["datasets"].append({"dataset": dataset, "status": status, **extra})
        if status == "ok":
            result["summary"]["ok_dataset_count"] += 1
        elif status == "failed":
            result["summary"]["failed_dataset_count"] += 1
        elif status == "skipped":
            result["summary"]["skipped_dataset_count"] += 1

    for dataset in datasets:
        if args.incremental and not args.refresh and not _should_sync_incrementally(service, dataset, ticker):
            record_dataset(dataset, "skipped", reason="fresh_in_local_cache")
            continue

        _log(args.verbose, f"[sync] ticker={ticker} dataset={dataset}")
        if dataset == "company":
            try:
                company = _retry_call(
                    f"{ticker}:company",
                    lambda: service.get_company(ticker, refresh=args.refresh),
                    retries=args.retries,
                    backoff_seconds=args.retry_backoff_seconds,
                    verbose=args.verbose,
                )
                result["company_name"] = company.name
                record_dataset("company", "ok", source=company.source)
            except Exception as exc:
                errors["company_error"] = str(exc)
                record_dataset("company", "failed", error=str(exc))
        elif dataset == "financials":
            try:
                financials = _retry_call(
                    f"{ticker}:financials",
                    lambda: service.list_financials(ticker, limit=4, refresh=args.refresh),
                    retries=args.retries,
                    backoff_seconds=args.retry_backoff_seconds,
                    verbose=args.verbose,
                )
                result["financial_count"] = len(financials)
                record_dataset("financials", "ok", count=len(financials))
            except Exception as exc:
                errors["financial_error"] = str(exc)
                record_dataset("financials", "failed", error=str(exc))
        elif dataset == "prices":
            try:
                prices_debug = _retry_call(
                    f"{ticker}:prices",
                    lambda: service.list_prices_with_debug(ticker, limit=args.price_limit, refresh=args.refresh),
                    retries=args.retries,
                    backoff_seconds=args.retry_backoff_seconds,
                    verbose=args.verbose,
                )
                result["price_count"] = len(prices_debug.items)
                result["price_debug"] = [item.model_dump() for item in prices_debug.debug]
                record_dataset("prices", "ok", count=len(prices_debug.items))
            except Exception as exc:
                errors["price_error"] = str(exc)
                record_dataset("prices", "failed", error=str(exc))
        elif dataset == "events":
            try:
                events_debug = _retry_call(
                    f"{ticker}:events",
                    lambda: service.list_events_with_debug(ticker, limit=args.event_limit, refresh=args.refresh),
                    retries=args.retries,
                    backoff_seconds=args.retry_backoff_seconds,
                    verbose=args.verbose,
                )
                result["event_count"] = len(events_debug.items)
                result["event_debug"] = [item.model_dump() for item in events_debug.debug]
                record_dataset("events", "ok", count=len(events_debug.items))
            except Exception as exc:
                errors["event_error"] = str(exc)
                record_dataset("events", "failed", error=str(exc))
        elif dataset == "overview":
            try:
                overview = _retry_call(
                    f"{ticker}:overview",
                    lambda: service.get_overview(ticker, refresh=False),
                    retries=args.retries,
                    backoff_seconds=args.retry_backoff_seconds,
                    verbose=args.verbose,
                )
                result["overview"] = {
                    "company_name": overview.company.data.name if overview.company.data else None,
                    "latest_financial_date": overview.latest_financial.data.report_date if overview.latest_financial.data else None,
                    "latest_price_date": overview.latest_price.data.trade_date if overview.latest_price.data else None,
                    "risk_flag_count": len(overview.risk_flags.data),
                    "section_status": {
                        "company": overview.company.data_status.model_dump(),
                        "latest_financial": overview.latest_financial.data_status.model_dump(),
                        "latest_price": overview.latest_price.data_status.model_dump(),
                        "recent_events": overview.recent_events.data_status.model_dump(),
                        "risk_flags": overview.risk_flags.data_status.model_dump(),
                        "signals": overview.signals.data_status.model_dump(),
                    },
                }
                record_dataset("overview", "ok")
            except Exception as exc:
                errors["overview_error"] = str(exc)
                record_dataset("overview", "failed", error=str(exc))

    if errors:
        result["status"] = "partial"
        result.update(errors)
    return result


def main() -> None:
    args = parse_args()
    service = get_stock_data_service()
    tickers = _parse_tickers(args.tickers)
    datasets = _selected_datasets(args)
    if args.dry_run:
        results = [_dry_run_result(ticker, datasets, args.incremental) for ticker in tickers]
    else:
        results = [_sync_ticker(service, ticker, args, datasets) for ticker in tickers]

    failures = [
        {
            "ticker": item["ticker"],
            "errors": {key: value for key, value in item.items() if key.endswith("_error")},
        }
        for item in results
        if any(key.endswith("_error") for key in item)
    ]
    payload = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "mode": "dry_run" if args.dry_run else ("incremental" if args.incremental else "full"),
        "selected_datasets": datasets,
        "results": results,
        "summary": {
            "ticker_count": len(results),
            "ok_ticker_count": sum(1 for item in results if item["status"] == "ok"),
            "partial_ticker_count": sum(1 for item in results if item["status"] == "partial"),
            "dry_run_ticker_count": sum(1 for item in results if item["status"] == "dry_run"),
        },
        "failure_count": len(failures),
        "failures": failures,
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.json_report:
        Path(args.json_report).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
