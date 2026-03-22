import hashlib
import re
from datetime import datetime
from typing import Any

from app.models.stock import CompanyProfile, Event, FinancialSummary, PriceDaily

SOURCE_PRIORITY = {
    "tushare": 100,
    "cninfo": 100,
    "akshare": 90,
    "exchange_search": 60,
    "fallback": 10,
    "derived": 0,
}

EVENT_TYPE_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("financial_report", ("年报", "半年报", "季度报告", "annual report", "financial summary")),
    ("earnings_forecast", ("业绩预告", "业绩快报", "业绩预增", "业绩预减")),
    ("regulatory_action", ("监管函", "问询", "关注函", "处罚", "立案")),
    ("shareholder_change", ("减持", "增持", "股东变动", "股份变动")),
    ("capital_operation", ("回购", "定增", "配股", "融资", "可转债")),
    ("asset_restructuring", ("并购", "重组", "收购", "出售资产")),
    ("pledge", ("质押", "解除质押")),
]

POSITIVE_EVENT_KEYWORDS = ("增持", "回购", "中标", "签署", "增长", "预增")
NEGATIVE_EVENT_KEYWORDS = ("减持", "监管", "问询", "处罚", "立案", "风险", "质押", "预减", "亏损")


def normalize_ticker_input(ticker: str) -> str:
    cleaned = ticker.strip().upper()
    if re.fullmatch(r"\d{6}\.(SH|SZ|BJ)", cleaned):
        return cleaned
    if re.fullmatch(r"(SH|SZ|BJ)\d{6}", cleaned):
        return f"{cleaned[2:]}.{cleaned[:2]}"
    if re.fullmatch(r"\d{6}", cleaned):
        if cleaned.startswith(("4", "8")):
            return f"{cleaned}.BJ"
        if cleaned.startswith(("5", "6", "9")):
            return f"{cleaned}.SH"
        return f"{cleaned}.SZ"
    raise ValueError(f"Unsupported ticker format: {ticker}")


def get_cninfo_exchange_code(market: str) -> str:
    mapping = {"SZ": "sz", "SH": "sh", "BJ": "bj"}
    return mapping.get(market, market.lower())


def format_compact_date(value: str) -> str:
    return value.replace("-", "")


def normalize_date(value: Any) -> str | None:
    if value in {None, ""}:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    text = str(value).strip()
    if not text:
        return None
    if re.fullmatch(r"\d{8}", text):
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text
    if len(text) >= 10:
        candidate = text[:10]
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", candidate):
            return candidate
    return text


def to_float(value: Any) -> float | None:
    if value in {None, "", "--"}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_int(value: Any) -> int | None:
    if value in {None, "", "--"}:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def normalize_company_profile(ticker: str, raw: dict[str, Any]) -> CompanyProfile:
    normalized = normalize_ticker_input(ticker)
    basic = raw.get("basic", {})
    company = raw.get("company", {})
    market = normalized.split(".", maxsplit=1)[1]
    exchange = {"SH": "SSE", "SZ": "SZSE", "BJ": "BSE"}.get(market, market)
    return CompanyProfile(
        ticker=normalized,
        name=basic.get("name"),
        exchange=exchange,
        market=basic.get("market"),
        industry=basic.get("industry"),
        area=basic.get("area") or company.get("province"),
        list_date=normalize_date(basic.get("list_date")),
        status=basic.get("list_status"),
        website=company.get("website"),
        chairman=company.get("chairman"),
        manager=company.get("manager"),
        employees=to_int(company.get("employees")),
        main_business=company.get("main_business"),
        business_scope=company.get("business_scope"),
        source="tushare",
        dedupe_key=normalized,
        source_priority=get_source_priority("tushare"),
        raw=raw,
    )


def get_source_priority(source: str | None) -> int:
    return SOURCE_PRIORITY.get(str(source or "").strip().lower(), 0)


def should_replace_by_source_priority(current_source: str | None, candidate_source: str | None) -> bool:
    return get_source_priority(candidate_source) >= get_source_priority(current_source)


def build_event_dedupe_key(ticker: str, title: str, event_date: str | None, url: str | None = None) -> str:
    normalized = normalize_ticker_input(ticker)
    normalized_title = re.sub(r"\s+", " ", (title or "").strip().lower())
    normalized_url = (url or "").strip().lower()
    digest = hashlib.sha1(f"{normalized}|{event_date or ''}|{normalized_title}|{normalized_url}".encode("utf-8")).hexdigest()[:20]
    return f"{normalized}:{digest}"


def normalize_event_type(title: str, category: str | None = None) -> str:
    haystack = f"{category or ''} {title}".lower()
    for event_type, keywords in EVENT_TYPE_RULES:
        if any(keyword.lower() in haystack for keyword in keywords):
            return event_type
    return "general_disclosure"


def normalize_event_importance(title: str, summary: str | None = None, event_type: str | None = None) -> str:
    haystack = f"{title} {summary or ''}"
    if event_type in {"regulatory_action", "asset_restructuring", "earnings_forecast"}:
        return "high"
    if any(keyword in haystack for keyword in ("年报", "减持", "增持", "问询", "监管函", "回购", "质押", "并购", "重组")):
        return "high"
    if event_type in {"financial_report", "shareholder_change", "capital_operation"}:
        return "medium"
    return "low"


def normalize_event_sentiment(title: str, summary: str | None = None) -> str:
    haystack = f"{title} {summary or ''}"
    if any(keyword in haystack for keyword in NEGATIVE_EVENT_KEYWORDS):
        return "negative"
    if any(keyword in haystack for keyword in POSITIVE_EVENT_KEYWORDS):
        return "positive"
    return "neutral"


def normalize_cninfo_event(ticker: str, raw: dict[str, Any]) -> Event:
    normalized = normalize_ticker_input(ticker)
    announcement_id = raw.get("announcementId") or raw.get("announcement_id")
    title = raw.get("announcementTitle") or raw.get("announcement_title") or raw.get("title") or "Untitled event"
    event_date = (
        normalize_date(raw.get("announcementTime"))
        or normalize_date(raw.get("announcement_time"))
        or normalize_date(raw.get("announcementDate"))
        or normalize_date(raw.get("announcement_date"))
    )
    adjunct = raw.get("adjunctUrl") or raw.get("adjunct_url")
    url = f"https://static.cninfo.com.cn/{adjunct.lstrip('/')}" if adjunct else None
    category = raw.get("announcementType") or raw.get("announcement_type")
    event_type = normalize_event_type(title=title, category=category)
    summary = raw.get("announcementContent") or raw.get("summary")
    dedupe_key = build_event_dedupe_key(normalized, title, event_date, url)
    if not announcement_id:
        announcement_id = dedupe_key
    return Event(
        event_id=str(announcement_id),
        dedupe_key=dedupe_key,
        ticker=normalized,
        event_date=event_date,
        title=title,
        raw_title=title,
        event_type=event_type,
        category=category,
        sentiment=normalize_event_sentiment(title, summary),
        source_type="filing",
        source="cninfo",
        source_priority=get_source_priority("cninfo"),
        url=url,
        summary=summary,
        importance=normalize_event_importance(title, summary, event_type),
        raw=raw,
    )


def normalize_financial_summary(ticker: str, raw: dict[str, Any]) -> FinancialSummary:
    normalized = normalize_ticker_input(ticker)
    report_date = normalize_date(raw.get("end_date")) or ""
    announcement_date = normalize_date(raw.get("ann_date"))
    record_id = f"{normalized}:{report_date}:{raw.get('report_type') or 'period'}"
    revenue = to_float(raw.get("total_revenue"))
    if revenue is None:
        revenue = to_float(raw.get("revenue"))
    return FinancialSummary(
        record_id=record_id,
        dedupe_key=record_id,
        ticker=normalized,
        report_date=report_date,
        announcement_date=announcement_date,
        report_type=raw.get("report_type"),
        revenue=revenue,
        revenue_yoy=to_float(raw.get("q_sales_yoy")),
        net_profit=to_float(raw.get("n_income")),
        net_profit_yoy=to_float(raw.get("q_dtprofit_yoy")),
        eps=to_float(raw.get("basic_eps")),
        roe=to_float(raw.get("roe")),
        gross_margin=to_float(raw.get("grossprofit_margin")),
        source="tushare",
        source_priority=get_source_priority("tushare"),
        raw=raw,
    )


def normalize_price_daily(ticker: str, raw: dict[str, Any]) -> PriceDaily:
    normalized = normalize_ticker_input(ticker)
    trade_date = normalize_date(raw.get("日期") or raw.get("trade_date")) or ""
    source = str(raw.get("source") or "akshare")
    return PriceDaily(
        ticker=normalized,
        trade_date=trade_date,
        dedupe_key=f"{normalized}:{trade_date}",
        open=to_float(raw.get("开盘") or raw.get("open")),
        high=to_float(raw.get("最高") or raw.get("high")),
        low=to_float(raw.get("最低") or raw.get("low")),
        close=to_float(raw.get("收盘") or raw.get("close")),
        volume=to_float(raw.get("成交量") or raw.get("volume")),
        amount=to_float(raw.get("成交额") or raw.get("amount")),
        change_pct=to_float(raw.get("涨跌幅") or raw.get("change_pct")),
        turnover_rate=to_float(raw.get("换手率") or raw.get("turnover_rate")),
        source=source,
        source_priority=get_source_priority(source),
        raw=raw,
    )


def extract_candidate_ticker(text: str) -> str | None:
    match = re.search(r"\b(?:SH|SZ|BJ)?\d{6}(?:\.(?:SH|SZ|BJ))?\b", text.upper())
    if not match:
        return None
    return normalize_ticker_input(match.group(0))
