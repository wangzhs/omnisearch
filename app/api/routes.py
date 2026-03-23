from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings
from app.extractors.content import extract_content
from app.normalizers.stock import extract_candidate_ticker, normalize_ticker_input
from app.providers.searxng import search_web
from app.research.planners.factory import get_research_planner
from app.schemas.extract import ExtractRequest, ExtractResponse
from app.schemas.research import ResearchItem, ResearchRequest, ResearchResponse, ResearchSearchDebugItem
from app.schemas.search import SearchRequest, SearchResponse, SearchResult
from app.schemas.stock import (
    CompanyDebugResponse,
    CompanyOverview,
    OverviewDebugResponse,
    CompanyProfile,
    EventListDebugResponse,
    Event,
    FinancialListDebugResponse,
    FinancialSummary,
    PriceDaily,
    PriceListDebugResponse,
    RiskFlag,
    StockEndpointDebug,
    StockPaginationDebug,
    TimelineItem,
)
from app.services.stock import get_stock_data_service

router = APIRouter()


@router.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/db")
def health_db() -> dict:
    service = get_stock_data_service()
    return {
        "status": "ok" if service.repository.ping() else "failed",
        "backend": "sqlite",
    }


@router.get("/health/sources")
def health_sources() -> dict:
    return {
        "status": "ok",
        "sources": {
            "tushare": {"configured": bool(settings.tushare_token), "base_url": settings.tushare_base_url},
            "cninfo": {"configured": bool(settings.cninfo_announcements_url), "url": settings.cninfo_announcements_url},
            "akshare": {"configured": True},
        },
    }


@router.get("/health/sync")
def health_sync(ticker: str | None = None) -> dict:
    service = get_stock_data_service()
    normalized_ticker = normalize_ticker_input(ticker) if ticker else None
    items = service.repository.list_sync_state(ticker=normalized_ticker)
    return {
        "status": "ok",
        "ticker": normalized_ticker,
        "summary": _build_sync_health_summary(items),
        "items": items,
    }


@router.post("/search", response_model=SearchResponse)
def search(request: SearchRequest) -> SearchResponse:
    try:
        results = search_web(
            query=request.query,
            top_k=request.top_k,
            searxng_base_url=settings.searxng_base_url,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return SearchResponse(query=request.query, results=results)


@router.post("/extract", response_model=ExtractResponse)
def extract(request: ExtractRequest) -> ExtractResponse:
    try:
        result = extract_content(str(request.url))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return result


@router.post("/research", response_model=ResearchResponse)
def research(request: ResearchRequest) -> ResearchResponse:
    planner = get_research_planner()
    queries = planner.build_queries(request.query)
    aggregated_results: list[SearchResult] = []
    search_debug: list[ResearchSearchDebugItem] = []
    seen_urls: set[str] = set()

    for query in queries:
        try:
            query_results = search_web(
                query=query,
                top_k=request.top_k,
                searxng_base_url=settings.searxng_base_url,
            )
            search_debug.append(
                ResearchSearchDebugItem(
                    query=query,
                    result_count=len(query_results),
                )
            )
        except RuntimeError as exc:
            search_debug.append(
                ResearchSearchDebugItem(
                    query=query,
                    result_count=0,
                    error=str(exc),
                )
            )
            continue

        for result in query_results:
            if result.url in seen_urls:
                continue
            seen_urls.add(result.url)
            aggregated_results.append(result)

    total_search_results = len(aggregated_results)
    items: list[ResearchItem] = []
    successful_extracts = 0
    for result in aggregated_results:
        try:
            extracted = extract_content(result.url)
            items.append(ResearchItem(search_result=result, extracted=extracted))
            successful_extracts += 1
        except RuntimeError as exc:
            items.append(ResearchItem(search_result=result, error=str(exc)))
            continue

        if successful_extracts >= request.top_k:
            break

    stock_context = None
    candidate_ticker = extract_candidate_ticker(request.query)
    if candidate_ticker:
        try:
            stock_context = get_stock_data_service().get_research_context(candidate_ticker)
        except Exception:
            stock_context = None

    return ResearchResponse(
        query=request.query,
        status="ok",
        generated_queries=queries,
        search_results_count=total_search_results,
        search_debug=search_debug,
        items=items,
        stock_context=stock_context,
    )


@router.get("/company/{ticker}", response_model=CompanyProfile | CompanyDebugResponse)
def get_company(ticker: str, refresh: bool = False, debug: bool = False) -> CompanyProfile | CompanyDebugResponse:
    try:
        service = get_stock_data_service()
        if debug:
            return service.get_company_with_debug(ticker, refresh=refresh)
        return service.get_company(ticker, refresh=refresh)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/company/{ticker}/events", response_model=list[Event] | EventListDebugResponse)
def get_company_events(
    ticker: str,
    limit: int = 20,
    refresh: bool = False,
    debug: bool = False,
    event_type: str | None = None,
    importance: str | None = None,
    source: str | None = None,
    sentiment: str | None = None,
    sort_by: str = Query(default="event_date", pattern="^(event_date|importance|updated_at)$"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> list[Event] | EventListDebugResponse:
    try:
        if debug:
            payload = get_stock_data_service().list_events_with_debug(ticker, limit=max(limit, page * page_size), refresh=refresh)
            filtered = _filter_events(_get_payload_items(payload), event_type=event_type, importance=importance, source=source, sentiment=sentiment)
            items = _paginate_events(
                filtered,
                sort_by=sort_by,
                sort_order=sort_order,
                page=page,
                page_size=page_size,
            )
            _set_payload_items(payload, items)
            _set_payload_debug_pagination(
                payload,
                limit=limit,
                page=page,
                page_size=page_size,
                returned_items=len(items),
                total_items=len(filtered),
                sort_by=sort_by,
                sort_order=sort_order,
            )
            return payload
        items = get_stock_data_service().list_events(ticker, limit=max(limit, page * page_size), refresh=refresh)
        return _paginate_events(
            _filter_events(items, event_type=event_type, importance=importance, source=source, sentiment=sentiment),
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/company/{ticker}/financials", response_model=list[FinancialSummary] | FinancialListDebugResponse)
def get_company_financials(
    ticker: str,
    limit: int = 8,
    refresh: bool = False,
    debug: bool = False,
    report_type: str | None = None,
    sort_by: str = Query(default="report_date", pattern="^(report_date|announcement_date|revenue|net_profit)$"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=8, ge=1, le=100),
) -> list[FinancialSummary] | FinancialListDebugResponse:
    try:
        service = get_stock_data_service()
        if debug:
            payload = service.list_financials_with_debug(ticker, limit=max(limit, page * page_size), refresh=refresh)
            filtered = _get_payload_items(payload)
            if report_type:
                filtered = [item for item in filtered if _item_value(item, "report_type") == report_type]
            ordered = sorted(filtered, key=lambda item: _sort_value(_item_value(item, sort_by)), reverse=(sort_order == "desc"))
            items = _paginate_list(ordered, page=page, page_size=page_size)
            _set_payload_items(payload, items)
            _set_payload_debug_pagination(
                payload,
                limit=limit,
                page=page,
                page_size=page_size,
                returned_items=len(items),
                total_items=len(filtered),
                sort_by=sort_by,
                sort_order=sort_order,
            )
            return payload
        items = service.list_financials(ticker, limit=max(limit, page * page_size), refresh=refresh)
        if report_type:
            items = [item for item in items if _item_value(item, "report_type") == report_type]
        items = sorted(items, key=lambda item: _sort_value(_item_value(item, sort_by)), reverse=(sort_order == "desc"))
        return _paginate_list(items, page=page, page_size=page_size)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/company/{ticker}/prices", response_model=list[PriceDaily] | PriceListDebugResponse)
def get_company_prices(
    ticker: str,
    limit: int = 60,
    start_date: str | None = None,
    end_date: str | None = None,
    refresh: bool = False,
    debug: bool = False,
    sort_order: str = Query(default="asc", pattern="^(asc|desc)$"),
    min_change_pct: float | None = None,
    max_change_pct: float | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=60, ge=1, le=200),
) -> list[PriceDaily] | PriceListDebugResponse:
    try:
        if debug:
            payload = get_stock_data_service().list_prices_with_debug(
                ticker,
                limit=max(limit, page * page_size),
                start_date=start_date,
                end_date=end_date,
                refresh=refresh,
            )
            filtered = _filter_prices(_get_payload_items(payload), min_change_pct=min_change_pct, max_change_pct=max_change_pct)
            items = _paginate_prices(
                filtered,
                sort_order=sort_order,
                page=page,
                page_size=page_size,
            )
            _set_payload_items(payload, items)
            _set_payload_debug_pagination(
                payload,
                limit=limit,
                page=page,
                page_size=page_size,
                returned_items=len(items),
                total_items=len(filtered),
                sort_by="trade_date",
                sort_order=sort_order,
            )
            return payload
        items = get_stock_data_service().list_prices(
            ticker,
            limit=max(limit, page * page_size),
            start_date=start_date,
            end_date=end_date,
            refresh=refresh,
        )
        return _paginate_prices(
            _filter_prices(items, min_change_pct=min_change_pct, max_change_pct=max_change_pct),
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get(
    "/company/{ticker}/overview",
    response_model=CompanyOverview | OverviewDebugResponse,
    responses={
        200: {
            "description": "Stable A-share company overview contract with per-section data status.",
            "content": {
                "application/json": {
                    "examples": {
                        "fresh": {
                            "summary": "Fresh overview",
                            "value": CompanyOverview.model_config["json_schema_extra"]["example"],
                        },
                        "missing_company": {
                            "summary": "Fallback company profile with missing upstream data",
                            "value": {
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
                                    },
                                    "data_status": {
                                        "status": "missing",
                                        "updated_at": None,
                                        "source": "tushare",
                                        "ttl_hours": 24,
                                        "cache_hit": False,
                                        "error_message": None,
                                    },
                                },
                                "latest_financial": {"data": None, "data_status": {"status": "missing", "updated_at": None, "source": "tushare", "ttl_hours": 24, "cache_hit": False, "error_message": None}},
                                "latest_price": {"data": None, "data_status": {"status": "missing", "updated_at": None, "source": None, "ttl_hours": 24, "cache_hit": False, "error_message": None}},
                                "recent_events": {"data": [], "data_status": {"status": "missing", "updated_at": None, "source": None, "ttl_hours": 24, "cache_hit": False, "error_message": None}},
                                "risk_flags": {"data": [], "data_status": {"status": "missing", "updated_at": None, "source": "derived", "ttl_hours": 24, "cache_hit": True, "error_message": None}},
                                "signals": {"data": [], "data_status": {"status": "missing", "updated_at": None, "source": "derived", "ttl_hours": 24, "cache_hit": True, "error_message": None}},
                            },
                        },
                        "stale_data": {
                            "summary": "Cached overview with stale upstream freshness",
                            "value": {
                                "ticker": "600036.SH",
                                "company": {
                                    "data": {"ticker": "600036.SH", "name": "China Merchants Bank", "source": "tushare", "updated_at": "2026-03-10T00:00:00Z"},
                                    "data_status": {"status": "stale", "updated_at": "2026-03-10T00:00:00Z", "source": "tushare", "ttl_hours": 24, "cache_hit": True, "error_message": "Upstream request timed out."},
                                },
                                "latest_financial": {"data": None, "data_status": {"status": "stale", "updated_at": "2026-03-10T00:00:00Z", "source": "tushare", "ttl_hours": 24, "cache_hit": True, "error_message": None}},
                                "latest_price": {"data": None, "data_status": {"status": "failed", "updated_at": None, "source": "akshare", "ttl_hours": 24, "cache_hit": False, "error_message": "eastmoney unavailable"}},
                                "recent_events": {"data": [], "data_status": {"status": "missing", "updated_at": None, "source": None, "ttl_hours": 24, "cache_hit": False, "error_message": None}},
                                "risk_flags": {"data": [], "data_status": {"status": "failed", "updated_at": "2026-03-10T00:00:00Z", "source": "derived", "ttl_hours": 24, "cache_hit": True, "error_message": None}},
                                "signals": {"data": [], "data_status": {"status": "failed", "updated_at": "2026-03-10T00:00:00Z", "source": "derived", "ttl_hours": 24, "cache_hit": True, "error_message": None}},
                            },
                        },
                    }
                }
            },
        }
    },
)
def get_company_overview(ticker: str, refresh: bool = False, debug: bool = False) -> CompanyOverview | OverviewDebugResponse:
    try:
        service = get_stock_data_service()
        if debug:
            return service.get_overview_with_debug(ticker, refresh=refresh)
        return service.get_overview(ticker, refresh=refresh)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/company/{ticker}/timeline", response_model=list[TimelineItem])
def get_company_timeline(ticker: str, refresh: bool = False) -> list[TimelineItem]:
    try:
        return get_stock_data_service().get_timeline(ticker, refresh=refresh)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/company/{ticker}/risk-flags", response_model=list[RiskFlag])
def get_company_risk_flags(ticker: str, refresh: bool = False) -> list[RiskFlag]:
    try:
        return get_stock_data_service().get_risk_flags(ticker, refresh=refresh)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _filter_events(
    items: list[Event],
    event_type: str | None,
    importance: str | None,
    source: str | None,
    sentiment: str | None,
) -> list[Event]:
    filtered = items
    if event_type:
        filtered = [item for item in filtered if _item_value(item, "event_type") == event_type]
    if importance:
        filtered = [item for item in filtered if _item_value(item, "importance") == importance]
    if source:
        filtered = [item for item in filtered if _item_value(item, "source") == source]
    if sentiment:
        filtered = [item for item in filtered if _item_value(item, "sentiment") == sentiment]
    return filtered


def _paginate_events(items: list[Event], sort_by: str, sort_order: str, page: int, page_size: int) -> list[Event]:
    importance_rank = {"high": 3, "medium": 2, "low": 1, None: 0}
    if sort_by == "importance":
        ordered = sorted(items, key=lambda item: importance_rank.get(_item_value(item, "importance"), 0), reverse=(sort_order == "desc"))
    else:
        ordered = sorted(items, key=lambda item: _item_value(item, sort_by) or "", reverse=(sort_order == "desc"))
    return _paginate_list(ordered, page=page, page_size=page_size)


def _filter_prices(items: list[PriceDaily], min_change_pct: float | None, max_change_pct: float | None) -> list[PriceDaily]:
    filtered = items
    if min_change_pct is not None:
        filtered = [
            item for item in filtered if _item_value(item, "change_pct") is not None and _item_value(item, "change_pct") >= min_change_pct
        ]
    if max_change_pct is not None:
        filtered = [
            item for item in filtered if _item_value(item, "change_pct") is not None and _item_value(item, "change_pct") <= max_change_pct
        ]
    return filtered


def _paginate_prices(items: list[PriceDaily], sort_order: str, page: int, page_size: int) -> list[PriceDaily]:
    ordered = sorted(items, key=lambda item: _item_value(item, "trade_date") or "", reverse=(sort_order == "desc"))
    return _paginate_list(ordered, page=page, page_size=page_size)


def _build_sync_health_summary(items: list[dict]) -> dict:
    ok_count = sum(1 for item in items if item.get("status") == "ok")
    partial_count = sum(1 for item in items if item.get("status") == "partial")
    failed_count = sum(1 for item in items if item.get("status") == "failed")

    if failed_count:
        status = "failed"
    elif partial_count:
        status = "partial"
    else:
        status = "ok"

    degraded_rows = [item for item in items if item.get("status") in {"partial", "failed"}]
    latest_degraded = None
    if degraded_rows:
        latest_degraded = max(
            degraded_rows,
            key=lambda item: (
                item.get("last_error_at") or "",
                item.get("last_synced_at") or item.get("synced_at") or "",
                item.get("dataset") or "",
            ),
        )

    return {
        "status": status,
        "ok_count": ok_count,
        "partial_count": partial_count,
        "failed_count": failed_count,
        "latest_degraded_dataset": latest_degraded.get("dataset") if latest_degraded else None,
    }


def _set_payload_items(payload, items: list) -> None:
    if isinstance(payload, dict):
        payload["items"] = items
        return
    payload.items = items


def _set_payload_debug_pagination(
    payload,
    *,
    limit: int,
    page: int,
    page_size: int,
    returned_items: int,
    total_items: int,
    sort_by: str,
    sort_order: str,
) -> None:
    debug = payload["debug"] if isinstance(payload, dict) else payload.debug
    if isinstance(debug, dict):
        debug["pagination"] = {
            "limit": limit,
            "page": page,
            "page_size": page_size,
            "returned_items": returned_items,
            "total_items": total_items,
            "sort_by": sort_by,
            "sort_order": sort_order,
        }
        return
    debug.pagination = StockPaginationDebug(
        limit=limit,
        page=page,
        page_size=page_size,
        returned_items=returned_items,
        total_items=total_items,
        sort_by=sort_by,
        sort_order=sort_order,
    )


def _paginate_list(items: list, page: int, page_size: int) -> list:
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end]


def _get_payload_items(payload) -> list:
    if isinstance(payload, dict):
        return payload.get("items", [])
    return payload.items


def _item_value(item, field: str):
    if isinstance(item, dict):
        return item.get(field)
    return getattr(item, field)


def _sort_value(value):
    if value is None:
        return ""
    return value
