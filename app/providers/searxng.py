from typing import Any

import requests

from app.core.config import settings
from app.schemas.search import SearchResult


def search_web(query: str, top_k: int, searxng_base_url: str) -> list[SearchResult]:
    url = f"{searxng_base_url.rstrip('/')}/search"
    params = {
        "q": query,
        "format": "json",
    }
    headers = {"User-Agent": settings.user_agent}

    try:
        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=settings.request_timeout,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Failed to query SearXNG: {exc}") from exc

    payload = response.json()
    raw_results = payload.get("results", [])
    return [_normalize_result(item) for item in raw_results[:top_k]]


def _normalize_result(item: dict[str, Any]) -> SearchResult:
    return SearchResult(
        title=item.get("title") or "",
        url=item.get("url") or "",
        snippet=item.get("content") or item.get("snippet") or "",
        source=item.get("engine") or item.get("source") or "searxng",
        score=_coerce_score(item.get("score")),
    )


def _coerce_score(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

