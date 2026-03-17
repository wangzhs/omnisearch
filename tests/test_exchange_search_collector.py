from app.collectors.exchange_search import ExchangeSearchCollector


def test_exchange_search_extracts_event_date_from_url() -> None:
    collector = ExchangeSearchCollector()

    event_date = collector._extract_event_date(
        "https://disc.static.szse.cn/download/disc/disk03/finalpage/2025-12-23/test.pdf",
        "test",
        "",
    )

    assert event_date == "2025-12-23"


def test_exchange_search_filters_irrelevant_results() -> None:
    collector = ExchangeSearchCollector()

    assert collector._is_relevant_result(
        title="深圳市英维克科技股份有限公司关于年报的公告",
        snippet="002837 英维克 2025年半年度报告摘要",
        aliases={"002837", "英维克"},
    )
    assert not collector._is_relevant_result(
        title="宁波惠康工业科技股份有限公司",
        snippet="其他公司公告",
        aliases={"002837", "英维克"},
    )


def test_exchange_search_skips_navigation_and_low_signal_results() -> None:
    collector = ExchangeSearchCollector()

    assert collector._should_skip_result(
        title="002837 英维克",
        url="http://www.szse.cn/certificate/individual/index.html?code=002837",
        snippet="",
    )
    assert collector._should_skip_result(
        title="深圳市英维克科技股份有限公司 投资者关系管理制度",
        url="https://disc.static.szse.cn/test.pdf",
        snippet="",
    )
    assert collector._should_skip_result(
        title="— 1 — 附件1 融资融券标的股票名单",
        url="https://docs.static.szse.cn/test.pdf",
        snippet="002837 英维克",
    )


def test_exchange_search_marks_high_signal_events() -> None:
    collector = ExchangeSearchCollector()

    assert collector._compute_importance(
        title="深圳市英维克科技股份有限公司关于股东减持计划的公告",
        snippet="",
    ) == "high"


def test_exchange_search_normalizes_duplicate_szse_urls() -> None:
    collector = ExchangeSearchCollector()

    url = "http://disc.static.szse.cn/download/disc/disk03/finalpage/2025-10-14/test.PDF"

    assert collector._normalize_event_url(url) == "https://disc.static.szse.cn/disc/disk03/finalpage/2025-10-14/test.PDF"
