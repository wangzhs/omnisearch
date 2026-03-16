from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.extractors.content import extract_content
from app.providers.searxng import search_web
from app.research.planners.factory import get_research_planner
from app.schemas.extract import ExtractRequest, ExtractResponse
from app.schemas.research import ResearchItem, ResearchRequest, ResearchResponse, ResearchSearchDebugItem
from app.schemas.search import SearchRequest, SearchResponse, SearchResult

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

    return ResearchResponse(
        query=request.query,
        status="ok",
        generated_queries=queries,
        search_results_count=total_search_results,
        search_debug=search_debug,
        items=items,
    )
