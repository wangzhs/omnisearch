from pydantic import BaseModel, Field

from app.schemas.extract import ExtractResponse
from app.schemas.search import SearchResult
from app.schemas.stock import StockResearchContext


class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=3, ge=1, le=10)


class ResearchItem(BaseModel):
    search_result: SearchResult
    extracted: ExtractResponse | None = None
    error: str | None = None


class ResearchSearchDebugItem(BaseModel):
    query: str
    result_count: int
    error: str | None = None


class ResearchResponse(BaseModel):
    query: str
    status: str
    generated_queries: list[str]
    search_results_count: int
    search_debug: list[ResearchSearchDebugItem]
    items: list[ResearchItem]
    stock_context: StockResearchContext | None = None
