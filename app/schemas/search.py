from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of results")


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    source: str
    score: float | None = None


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
