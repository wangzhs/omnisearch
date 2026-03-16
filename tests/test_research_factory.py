import sys
from types import SimpleNamespace

from app.research.planners.factory import get_research_planner


def test_factory_returns_llm_planner_when_configured(monkeypatch) -> None:
    monkeypatch.setattr("app.research.planners.factory.settings.research_planner", "llm")

    planner = get_research_planner()

    assert planner.name == "llm"


def test_llm_planner_safely_falls_back_to_rule_behavior(monkeypatch) -> None:
    monkeypatch.setattr("app.research.planners.factory.settings.research_planner", "llm")

    planner = get_research_planner()
    queries = planner.build_queries("英维克 业绩")

    assert "英维克 财报" in queries


def test_llm_planner_parses_model_output(monkeypatch) -> None:
    monkeypatch.setattr("app.research.planners.factory.settings.research_planner", "llm")
    monkeypatch.setattr("app.research.planners.llm.settings.openai_api_key", "test-key")

    class FakeChatCompletions:
        def create(self, model: str, messages: list[dict]):
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content='{"queries":["英维克 业绩","英维克 财报","Envicool earnings"]}'
                        )
                    )
                ]
            )

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=FakeChatCompletions())

    monkeypatch.setitem(sys.modules, "openai", type("FakeOpenAIModule", (), {"OpenAI": FakeOpenAI}))

    planner = get_research_planner()
    queries = planner.build_queries("英维克 业绩")

    assert queries == ["英维克 业绩", "英维克 财报", "Envicool earnings"]


def test_llm_planner_strips_think_from_chat_completions(monkeypatch) -> None:
    monkeypatch.setattr("app.research.planners.factory.settings.research_planner", "llm")
    monkeypatch.setattr("app.research.planners.llm.settings.openai_api_key", "test-key")

    class FakeChatCompletions:
        def create(self, model: str, messages: list[dict]):
            content = '<think>internal reasoning</think>\n{"queries":["notion vs obsidian","notion vs obsidian comparison"]}'
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
            )

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=FakeChatCompletions())

    monkeypatch.setitem(sys.modules, "openai", type("FakeOpenAIModule", (), {"OpenAI": FakeOpenAI}))

    planner = get_research_planner()
    queries = planner.build_queries("notion vs obsidian")

    assert queries == ["notion vs obsidian", "notion vs obsidian comparison"]
