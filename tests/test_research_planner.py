from app.research.planners.rule_based import RuleBasedResearchPlanner


def test_rule_based_planner_keeps_original_query_and_expands_finance_terms() -> None:
    planner = RuleBasedResearchPlanner()

    queries = planner.build_queries("英维克 业绩")

    assert "英维克 业绩" in queries
    assert "英维克" in queries
    assert "英维克 财报" in queries
    assert "英维克 年报" in queries
    assert "Envicool earnings" in queries


def test_rule_based_planner_deduplicates_queries() -> None:
    planner = RuleBasedResearchPlanner()

    queries = planner.build_queries("  英维克   业绩  ")

    assert len(queries) == len(set(queries))
    assert queries[0] == "英维克 业绩"


def test_rule_based_planner_extracts_primary_entity_from_finance_query() -> None:
    planner = RuleBasedResearchPlanner()

    queries = planner.build_queries("英维克 业绩")

    assert queries[1] == "英维克"


def test_rule_based_planner_expands_technical_queries() -> None:
    planner = RuleBasedResearchPlanner()

    queries = planner.build_queries("fastapi websocket auth")

    assert "fastapi websocket auth docs" in queries
    assert "fastapi websocket auth example" in queries
    assert "fastapi websocket auth github" in queries


def test_rule_based_planner_expands_comparison_queries() -> None:
    planner = RuleBasedResearchPlanner()

    queries = planner.build_queries("notion vs obsidian")

    assert "notion vs obsidian comparison" in queries
    assert "notion vs obsidian pros cons" in queries


def test_rule_based_planner_expands_person_queries() -> None:
    planner = RuleBasedResearchPlanner()

    queries = planner.build_queries("马斯克 访谈")

    assert "马斯克 简介" in queries
    assert "马斯克 interview" in queries


def test_rule_based_planner_expands_news_event_queries() -> None:
    planner = RuleBasedResearchPlanner()

    queries = planner.build_queries("苹果 发布会")

    assert "苹果 发布会 新闻" in queries
    assert "苹果 发布会 latest" in queries


def test_rule_based_planner_expands_product_queries() -> None:
    planner = RuleBasedResearchPlanner()

    queries = planner.build_queries("notion pricing")

    assert "notion pricing review" in queries
    assert "notion pricing alternatives" in queries
