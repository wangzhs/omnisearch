import re

from app.research.planners.base import ResearchPlanner


class RuleBasedResearchPlanner(ResearchPlanner):
    INTENT_HINTS = {
        "业绩",
        "财报",
        "年报",
        "季报",
        "盈利",
        "营收",
        "收入",
        "利润",
        "earnings",
        "revenue",
        "price",
        "pricing",
        "review",
        "features",
        "best",
        "tool",
        "software",
        "发布",
        "公告",
        "政策",
        "新闻",
        "进展",
        "事件",
        "是谁",
        "采访",
        "访谈",
        "简介",
        "vs",
        "versus",
        "compare",
        "comparison",
        "alternatives",
        "api",
        "sdk",
        "error",
        "tutorial",
        "example",
        "docs",
        "websocket",
        "jwt",
    }

    @property
    def name(self) -> str:
        return "rule"

    def build_queries(self, query: str) -> list[str]:
        normalized = self._normalize_query(query)
        if not normalized:
            return []

        intent = self._detect_intent(normalized)
        primary_entity = self._extract_primary_entity(normalized)
        candidates = [
            normalized,
            primary_entity,
            *self._expand_intent_queries(normalized, intent),
            *self._expand_general_queries(normalized),
        ]

        deduped: list[str] = []
        seen: set[str] = set()
        for item in candidates:
            cleaned = self._normalize_query(item)
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                deduped.append(cleaned)

        return deduped[:8]

    def _detect_intent(self, query: str) -> str:
        lower_query = query.lower()

        if any(keyword in query for keyword in {"发布", "公告", "政策", "新闻", "进展", "事件"}):
            return "news_event"
        if any(keyword in query for keyword in {"业绩", "财报", "年报", "季报", "盈利", "营收", "收入", "利润"}):
            return "company_finance"
        if any(keyword in lower_query for keyword in {"earnings", "revenue", "annual report", "investor relations"}):
            return "company_finance"
        if any(keyword in lower_query for keyword in {" vs ", " versus ", "compare", "comparison", "alternatives"}):
            return "comparison"
        if any(keyword in lower_query for keyword in {"api", "sdk", "error", "tutorial", "example", "docs", "websocket", "jwt"}):
            return "technical"
        if any(keyword in lower_query for keyword in {"price", "pricing", "review", "features", "best", "tool", "software"}):
            return "product"
        if any(keyword in query for keyword in {"是谁", "采访", "访谈", "简介"}):
            return "person"
        return "general"

    def _expand_intent_queries(self, query: str, intent: str) -> list[str]:
        if intent == "company_finance":
            return self._expand_company_finance_queries(query)
        if intent == "technical":
            return self._expand_technical_queries(query)
        if intent == "comparison":
            return self._expand_comparison_queries(query)
        if intent == "person":
            return self._expand_person_queries(query)
        if intent == "news_event":
            return self._expand_news_event_queries(query)
        if intent == "product":
            return self._expand_product_queries(query)
        return []

    def _normalize_query(self, query: str) -> str:
        query = query.strip()
        query = re.sub(r"\s+", " ", query)
        query = query.replace("，", " ").replace("、", " ").replace("：", " ")
        query = re.sub(r"\s+", " ", query)
        return query.strip()

    def _expand_company_finance_queries(self, query: str) -> list[str]:
        terms = query.split()
        if not terms:
            return []

        finance_keywords = {"业绩", "财报", "年报", "季报", "盈利", "营收", "收入", "利润", "earnings", "revenue"}
        entity = terms[0]
        lower_query = query.lower()
        has_finance_intent = any(keyword in query for keyword in finance_keywords) or any(
            keyword in lower_query for keyword in finance_keywords
        )

        if not has_finance_intent:
            return []

        expansions = [
            f"{entity} 财报",
            f"{entity} 年报",
            f"{entity} 季报",
            f"{entity} 盈利",
            f"{entity} 营收",
        ]

        english_name = self._maybe_map_entity_to_english(entity)
        if english_name:
            expansions.extend(
                [
                    f"{english_name} earnings",
                    f"{english_name} annual report",
                    f"{english_name} investor relations",
                ]
            )

        expansions.append(f"{entity} 投资者关系")

        stock_code = self._extract_stock_code(query)
        if stock_code:
            expansions.append(f"{stock_code} 财报")

        return expansions

    def _expand_general_queries(self, query: str) -> list[str]:
        terms = query.split()
        if not terms:
            return []

        entity = self._extract_primary_entity(query)
        expansions = [entity]
        if len(terms) >= 2:
            expansions.append(f"{entity} {' '.join(terms[1:])}")
        return expansions

    def _expand_technical_queries(self, query: str) -> list[str]:
        expansions = [f"{query} docs", f"{query} example", f"{query} tutorial", f"{query} github"]
        return expansions

    def _expand_comparison_queries(self, query: str) -> list[str]:
        normalized = query.replace(" versus ", " vs ").replace(" compare ", " vs ").strip()
        expansions = [normalized, f"{normalized} comparison", f"{normalized} pros cons", f"{normalized} review"]
        return expansions

    def _expand_person_queries(self, query: str) -> list[str]:
        terms = query.split()
        if not terms:
            return []

        name = terms[0]
        expansions = [f"{name} 简介", f"{name} 访谈", f"{name} interview", f"{name} profile"]
        return expansions

    def _expand_news_event_queries(self, query: str) -> list[str]:
        expansions = [f"{query} 新闻", f"{query} 公告", f"{query} latest", f"{query} updates"]
        return expansions

    def _expand_product_queries(self, query: str) -> list[str]:
        expansions = [f"{query} review", f"{query} features", f"{query} pricing", f"{query} alternatives"]
        return expansions

    def _extract_stock_code(self, query: str) -> str | None:
        match = re.search(r"\b\d{6}\b", query)
        return match.group(0) if match else None

    def _maybe_map_entity_to_english(self, entity: str) -> str | None:
        entity_map = {
            "英维克": "Envicool",
        }
        return entity_map.get(entity)

    def _extract_primary_entity(self, query: str) -> str:
        terms = query.split()
        if not terms:
            return query

        entity_terms = [term for term in terms if term.lower() not in self.INTENT_HINTS and term not in self.INTENT_HINTS]
        if entity_terms:
            return " ".join(entity_terms)
        return terms[0]
