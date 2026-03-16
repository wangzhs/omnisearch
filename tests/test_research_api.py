from fastapi.testclient import TestClient

from app.main import app
from app.schemas.search import SearchResult


def test_research_returns_generated_queries_and_aggregated_items(monkeypatch) -> None:
    def fake_search_web(query: str, top_k: int, searxng_base_url: str):
        if query == "英维克 业绩":
            return [
                SearchResult(title="A", url="https://example.com/a", snippet="s1", source="searxng", score=1.0)
            ]
        if query == "英维克 财报":
            return [
                SearchResult(title="A duplicate", url="https://example.com/a", snippet="s1", source="searxng", score=1.0),
                SearchResult(title="B", url="https://example.com/b", snippet="s2", source="searxng", score=0.9),
            ]
        return []

    def fake_extract_content(url: str):
        return {
            "title": "Extracted",
            "url": url,
            "markdown": f"# {url}",
            "published_date": None,
            "domain": "example.com",
        }

    monkeypatch.setattr("app.api.routes.search_web", fake_search_web)
    monkeypatch.setattr("app.api.routes.extract_content", fake_extract_content)

    client = TestClient(app)
    response = client.post("/research", json={"query": "英维克 业绩", "top_k": 2})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["generated_queries"][0] == "英维克 业绩"
    assert payload["search_results_count"] == 2
    assert payload["search_debug"][0]["query"] == "英维克 业绩"
    assert payload["search_debug"][0]["result_count"] == 1
    assert len(payload["items"]) == 2
    assert payload["items"][0]["extracted"]["domain"] == "example.com"


def test_research_skips_failed_extracts_and_continues_until_success_limit(monkeypatch) -> None:
    def fake_search_web(query: str, top_k: int, searxng_base_url: str):
        if query == "英维克 业绩":
            return [
                SearchResult(title="A", url="https://example.com/a", snippet="s1", source="searxng", score=1.0),
                SearchResult(title="B", url="https://example.com/b", snippet="s2", source="searxng", score=0.9),
                SearchResult(title="C", url="https://example.com/c", snippet="s3", source="searxng", score=0.8),
            ]
        return []

    def fake_extract_content(url: str):
        if url in {"https://example.com/a", "https://example.com/b"}:
            raise RuntimeError("blocked")
        return {
            "title": "Extracted",
            "url": url,
            "markdown": f"# {url}",
            "published_date": None,
            "domain": "example.com",
        }

    monkeypatch.setattr("app.api.routes.search_web", fake_search_web)
    monkeypatch.setattr("app.api.routes.extract_content", fake_extract_content)

    client = TestClient(app)
    response = client.post("/research", json={"query": "英维克 业绩", "top_k": 1})

    assert response.status_code == 200
    payload = response.json()
    assert payload["search_results_count"] == 3
    assert len(payload["items"]) == 3
    assert payload["items"][0]["error"] == "blocked"
    assert payload["items"][1]["error"] == "blocked"
    assert payload["items"][2]["extracted"]["url"] == "https://example.com/c"
