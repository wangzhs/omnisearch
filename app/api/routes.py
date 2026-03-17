from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.extractors.content import extract_content
from app.normalizers.stock import extract_candidate_ticker
from app.providers.searxng import search_web
from app.research.planners.factory import get_research_planner
from app.schemas.extract import ExtractRequest, ExtractResponse
from app.schemas.research import ResearchItem, ResearchRequest, ResearchResponse, ResearchSearchDebugItem
from app.schemas.search import SearchRequest, SearchResponse, SearchResult
from app.schemas.stock import (
    CompanyOverview,
    CompanyProfile,
    EventListDebugResponse,
    Event,
    FinancialSummary,
    PriceDaily,
    PriceListDebugResponse,
    RiskFlag,
    TimelineItem,
)
from app.services.stock import get_stock_data_service

router = APIRouter()


@router.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


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


@router.get("/company/{ticker}", response_model=CompanyProfile)
def get_company(ticker: str, refresh: bool = False) -> CompanyProfile:
    try:
        return get_stock_data_service().get_company(ticker, refresh=refresh)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/company/{ticker}/events", response_model=list[Event] | EventListDebugResponse)
def get_company_events(ticker: str, limit: int = 20, refresh: bool = False, debug: bool = False) -> list[Event] | EventListDebugResponse:
    try:
        if debug:
            return get_stock_data_service().list_events_with_debug(ticker, limit=limit, refresh=refresh)
        return get_stock_data_service().list_events(ticker, limit=limit, refresh=refresh)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/company/{ticker}/financials", response_model=list[FinancialSummary])
def get_company_financials(ticker: str, limit: int = 8, refresh: bool = False) -> list[FinancialSummary]:
    try:
        return get_stock_data_service().list_financials(ticker, limit=limit, refresh=refresh)
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
) -> list[PriceDaily] | PriceListDebugResponse:
    try:
        if debug:
            return get_stock_data_service().list_prices_with_debug(
                ticker,
                limit=limit,
                start_date=start_date,
                end_date=end_date,
                refresh=refresh,
            )
        return get_stock_data_service().list_prices(
            ticker,
            limit=limit,
            start_date=start_date,
            end_date=end_date,
            refresh=refresh,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/company/{ticker}/overview", response_model=CompanyOverview)
def get_company_overview(ticker: str, refresh: bool = False) -> CompanyOverview:
    try:
        return get_stock_data_service().get_overview(ticker, refresh=refresh)
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
