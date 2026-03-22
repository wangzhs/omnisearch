import re

from app.core.config import settings
from app.normalizers.stock import (
    SOURCE_PRIORITY,
    build_event_dedupe_key,
    normalize_event_importance,
    normalize_event_sentiment,
    normalize_event_type,
    normalize_ticker_input,
)
from app.providers.searxng import search_web


class ExchangeSearchCollector:
    source = "exchange_search"
    LOW_SIGNAL_KEYWORDS = {
        "投资者关系管理制度",
        "战略发展委员会工作制度",
        "信息披露管理制度",
        "工作制度",
        "制度",
        "融资融券标的股票名单",
        "标的股票名单",
        "名单",
    }
    HIGH_SIGNAL_KEYWORDS = {
        "年报",
        "半年报",
        "季度报告",
        "业绩预告",
        "监管函",
        "问询",
        "减持",
        "质押",
        "回购",
        "并购",
        "重组",
    }

    def fetch_events(
        self,
        ticker: str,
        company_name: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        return self.fetch_events_with_debug(ticker=ticker, company_name=company_name, limit=limit)["items"]

    def fetch_events_with_debug(
        self,
        ticker: str,
        company_name: str | None = None,
        limit: int = 10,
    ) -> dict:
        normalized = normalize_ticker_input(ticker)
        symbol, market = normalized.split(".", maxsplit=1)
        domains = ["szse.cn"] if market == "SZ" else ["sse.com.cn"]
        keyword = company_name or symbol
        queries = [
            f"site:{domains[0]} {keyword} 公告",
            f"site:{domains[0]} {symbol} 信息披露",
            f"site:{domains[0]} {keyword} 年报",
        ]
        aliases = {symbol}
        if company_name:
            aliases.add(company_name)

        results: list[dict] = []
        seen_urls: set[str] = set()
        raw_count = 0
        for query in queries:
            try:
                items = search_web(
                    query=query,
                    top_k=limit,
                    searxng_base_url=settings.searxng_base_url,
                )
            except RuntimeError:
                continue
            for item in items:
                raw_count += 1
                if not any(domain in item.url for domain in domains):
                    continue
                normalized_url = self._normalize_event_url(item.url)
                if normalized_url in seen_urls:
                    continue
                if not self._is_relevant_result(item.title, item.snippet, aliases):
                    continue
                if self._should_skip_result(item.title, item.url, item.snippet):
                    continue
                seen_urls.add(normalized_url)
                event_date = self._extract_event_date(item.url, item.title, item.snippet)
                event_type = normalize_event_type(item.title, "exchange_disclosure")
                normalized_importance = self._compute_importance(item.title, item.snippet, event_type)
                normalized_url = self._normalize_event_url(item.url)
                results.append(
                    {
                        "event_id": build_event_dedupe_key(normalized, item.title, event_date, normalized_url),
                        "dedupe_key": build_event_dedupe_key(normalized, item.title, event_date, normalized_url),
                        "ticker": normalized,
                        "event_date": event_date,
                        "title": item.title,
                        "raw_title": item.title,
                        "event_type": event_type,
                        "category": "exchange_disclosure",
                        "sentiment": normalize_event_sentiment(item.title, item.snippet),
                        "source_type": "exchange_search",
                        "source": self.source,
                        "source_priority": SOURCE_PRIORITY[self.source],
                        "url": normalized_url,
                        "summary": item.snippet,
                        "importance": normalized_importance,
                        "raw": {
                            "query": query,
                            "title": item.title,
                            "url": item.url,
                            "snippet": item.snippet,
                            "source": item.source,
                        },
                    }
                )
                if len(results) >= limit:
                    sorted_results = self._sort_results(results)
                    return {
                        "items": sorted_results,
                        "debug": {
                            "source": self.source,
                            "status": "ok",
                            "count": raw_count,
                            "kept_count": len(sorted_results),
                            "error": None,
                        },
                    }
        sorted_results = self._sort_results(results)
        return {
            "items": sorted_results,
            "debug": {
                "source": self.source,
                "status": "ok" if sorted_results else "empty",
                "count": raw_count,
                "kept_count": len(sorted_results),
                "error": None,
            },
        }

    def _is_relevant_result(self, title: str, snippet: str, aliases: set[str]) -> bool:
        haystack = f"{title} {snippet}".lower()
        normalized_aliases = {alias.lower() for alias in aliases if alias}
        if not any(alias in haystack for alias in normalized_aliases):
            return False
        return True

    def _extract_event_date(self, url: str, title: str, snippet: str) -> str | None:
        candidates = [url, title, snippet]
        for text in candidates:
            match = re.search(r"(20\d{2})[-/](\d{2})[-/](\d{2})", text)
            if match:
                return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
            match = re.search(r"(20\d{2})(\d{2})(\d{2})", text)
            if match:
                return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
        return None

    def _should_skip_result(self, title: str, url: str, snippet: str) -> bool:
        if "certificate/individual/index.html" in url:
            return True
        if "查看更多行情" in title:
            return True
        haystack = f"{title} {snippet}"
        if any(keyword in haystack for keyword in self.LOW_SIGNAL_KEYWORDS):
            return True
        return False

    def _compute_importance(self, title: str, snippet: str, event_type: str | None = None) -> str:
        haystack = f"{title} {snippet}"
        if any(keyword in haystack for keyword in self.HIGH_SIGNAL_KEYWORDS):
            return "high"
        return normalize_event_importance(title, snippet, event_type)

    def _sort_results(self, results: list[dict]) -> list[dict]:
        return sorted(
            results,
            key=lambda item: ((item.get("event_date") or ""), item.get("title") or ""),
            reverse=True,
        )

    def _normalize_event_url(self, url: str) -> str:
        normalized = url.replace("http://", "https://")
        normalized = normalized.replace("/download/disc/", "/disc/")
        return normalized
