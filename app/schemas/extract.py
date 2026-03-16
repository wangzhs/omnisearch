from pydantic import BaseModel, Field, HttpUrl


class ExtractRequest(BaseModel):
    url: HttpUrl


class ExtractResponse(BaseModel):
    title: str | None = None
    url: str
    markdown: str = Field(..., description="Extracted page content in markdown")
    published_date: str | None = None
    domain: str
