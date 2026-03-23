from app.normalizers.stock import (
    build_event_dedupe_key,
    get_source_priority,
    normalize_company_profile,
    normalize_event_importance,
    normalize_cninfo_event,
    normalize_event_sentiment,
    normalize_event_title_for_dedupe,
    normalize_event_type,
    normalize_financial_summary,
    normalize_price_daily,
    should_replace_by_source_priority,
)


def test_event_normalization_applies_stable_taxonomy_and_sentiment() -> None:
    event = normalize_cninfo_event(
        "000001",
        {
            "announcementTitle": "关于股东减持计划的公告",
            "announcementTime": "2026-03-16",
            "announcementType": "公告",
            "adjunctUrl": "finalpage/test.pdf",
        },
    )

    assert event.event_type == "shareholder_change"
    assert event.sentiment == "negative"
    assert event.source_type == "filing"
    assert event.raw_title == "关于股东减持计划的公告"
    assert event.importance == "high"
    assert event.source_url == "https://static.cninfo.com.cn/finalpage/test.pdf"


def test_event_dedupe_key_is_stable() -> None:
    key1 = build_event_dedupe_key("000001", "年度报告", "2026-03-16", "https://example.com/a.pdf")
    key2 = build_event_dedupe_key("000001.SZ", "年度报告", "2026-03-16", "https://example.com/a.pdf")
    key3 = build_event_dedupe_key("000001.SZ", "年度报告", "2026-03-16", "https://example.com/b.pdf")

    assert key1 == key2
    assert key1 == key3
    assert normalize_event_type("关于年报的公告") == "financial_report"
    assert normalize_event_sentiment("公司回购计划") == "positive"


def test_event_dedupe_key_normalizes_title_variants() -> None:
    key1 = build_event_dedupe_key("000001.SZ", "关于 2026 年报的公告", "2026-03-16")
    key2 = build_event_dedupe_key("000001.SZ", "关于2026年报的公告", "2026-03-16")

    assert key1 == key2
    assert normalize_event_title_for_dedupe("关于 2026 年报的公告") == normalize_event_title_for_dedupe("关于2026年报的公告")


def test_event_title_normalization_collapses_punctuation_and_prefix_noise() -> None:
    normalized_plain = normalize_event_title_for_dedupe("关于2026年报的公告")
    normalized_spaced = normalize_event_title_for_dedupe("关于 2026 年报 的 公告")
    normalized_prefixed = normalize_event_title_for_dedupe("【公告】关于2026年报的公告")
    normalized_notice = normalize_event_title_for_dedupe("提示性公告：关于2026年报的公告")

    assert normalized_plain == normalized_spaced
    assert normalized_plain == normalized_prefixed
    assert normalized_plain == normalized_notice


def test_event_title_normalization_stays_conservative_for_unrelated_titles() -> None:
    annual_report = normalize_event_title_for_dedupe("关于2026年报的公告")
    shareholder_change = normalize_event_title_for_dedupe("关于股东减持计划的公告")

    assert annual_report != shareholder_change
    assert build_event_dedupe_key("000001.SZ", "关于2026年报的公告", "2026-03-16") != build_event_dedupe_key(
        "000001.SZ",
        "关于股东减持计划的公告",
        "2026-03-16",
    )


def test_event_taxonomy_covers_general_and_regulatory_cases() -> None:
    assert normalize_event_type("收到监管函") == "regulatory_action"
    assert normalize_event_type("关于召开股东大会的公告") == "general_disclosure"
    assert normalize_event_importance("关于召开股东大会的公告", event_type="general_disclosure") == "low"


def test_internal_stock_models_receive_explicit_dedupe_keys_and_source_priority() -> None:
    company = normalize_company_profile(
        "000001",
        {
            "basic": {"name": "平安银行", "market": "主板", "industry": "银行", "list_status": "L"},
            "company": {},
        },
    )
    financial = normalize_financial_summary(
        "000001",
        {"end_date": "20251231", "report_type": "annual", "n_income": 1.0},
    )
    price = normalize_price_daily(
        "000001",
        {"trade_date": "20260317", "close": 10.5, "source": "akshare"},
    )

    assert company.dedupe_key == "000001.SZ"
    assert company.source_priority == 100
    assert financial.dedupe_key == financial.record_id
    assert financial.source_priority == 100
    assert price.dedupe_key == "000001.SZ:2026-03-17"
    assert price.source_priority == 90


def test_source_priority_rules_are_explicit() -> None:
    assert get_source_priority("cninfo") > get_source_priority("exchange_search")
    assert should_replace_by_source_priority("exchange_search", "cninfo") is True
    assert should_replace_by_source_priority("cninfo", "exchange_search") is False
