from app.core.config import settings
from app.research.planners.base import ResearchPlanner
from app.research.planners.llm import LLMResearchPlanner
from app.research.planners.rule_based import RuleBasedResearchPlanner


def get_research_planner() -> ResearchPlanner:
    if settings.research_planner == "rule":
        return RuleBasedResearchPlanner()
    if settings.research_planner == "llm":
        return LLMResearchPlanner()

    # Keep a safe fallback until other planners are implemented.
    return RuleBasedResearchPlanner()
