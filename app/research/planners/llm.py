import json
import re

from app.core.config import settings
from app.research.planners.base import ResearchPlanner
from app.research.planners.rule_based import RuleBasedResearchPlanner


class LLMResearchPlanner(ResearchPlanner):
    """Skeleton planner for future model-backed query planning.

    For now it safely falls back to the rule-based planner so the workflow
    remains local-first and deterministic until an actual model integration is
    added.
    """

    def __init__(self) -> None:
        self._fallback = RuleBasedResearchPlanner()

    @property
    def name(self) -> str:
        return "llm"

    def build_queries(self, query: str) -> list[str]:
        if not settings.openai_api_key:
            return self._fallback.build_queries(query)

        try:
            from openai import OpenAI

            client_kwargs = {"api_key": settings.openai_api_key}
            if settings.openai_base_url:
                client_kwargs["base_url"] = settings.openai_base_url

            client = OpenAI(**client_kwargs)
            output_text = self._generate_with_chat_completions(client, query)
            queries = self._parse_queries(output_text)
            if queries:
                return queries
        except Exception:
            # Keep research usable even if the SDK is missing or the model call fails.
            pass

        return self._fallback.build_queries(query)

    def _build_prompt(self, query: str) -> str:
        fallback_queries = self._fallback.build_queries(query)
        prompt = {
            "task": "Generate concise search queries for a web research workflow.",
            "requirements": [
                "Return JSON only.",
                "Use the schema: {\"queries\": [string, ...]}",
                "Include the original query.",
                "Include an entity-only search query if the input contains an entity plus intent words.",
                "Expand with useful aliases, English variants, and likely search templates.",
                "Keep the list between 3 and 8 queries.",
                "Do not include explanations.",
            ],
            "query": query,
            "fallback_queries": fallback_queries,
        }
        return json.dumps(prompt, ensure_ascii=False)

    def _parse_queries(self, output_text: str) -> list[str]:
        if not output_text:
            return []

        output_text = self._strip_reasoning_blocks(output_text)
        output_text = self._extract_json_object(output_text)
        try:
            payload = json.loads(output_text)
        except json.JSONDecodeError:
            return []

        raw_queries = payload.get("queries")
        if not isinstance(raw_queries, list):
            return []

        cleaned: list[str] = []
        seen: set[str] = set()
        for item in raw_queries:
            if not isinstance(item, str):
                continue
            query = item.strip()
            if query and query not in seen:
                seen.add(query)
                cleaned.append(query)

        return cleaned[:8]

    def _generate_with_chat_completions(self, client, query: str) -> str:
        try:
            response = client.chat.completions.create(
                model=settings.research_planner_model,
                messages=[
                    {
                        "role": "user",
                        "content": self._build_prompt(query),
                    }
                ],
            )
        except Exception:
            return ""

        try:
            return response.choices[0].message.content or ""
        except (AttributeError, IndexError, TypeError):
            return ""

    def _strip_reasoning_blocks(self, text: str) -> str:
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
        return text.strip()

    def _extract_json_object(self, text: str) -> str:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end < start:
            return text
        return text[start : end + 1]
