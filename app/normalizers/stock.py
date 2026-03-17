import hashlib
import re
from datetime import datetime
from typing import Any

from app.models.stock import CompanyProfile, Event, FinancialSummary, PriceDaily


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
        raw=raw,
    )


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
    if not announcement_id:
        digest = hashlib.sha1(f"{normalized}|{title}|{event_date}".encode("utf-8")).hexdigest()[:16]
        announcement_id = f"{normalized}-{digest}"
    adjunct = raw.get("adjunctUrl") or raw.get("adjunct_url")
    url = f"https://static.cninfo.com.cn/{adjunct.lstrip('/')}" if adjunct else None
    return Event(
        event_id=str(announcement_id),
        ticker=normalized,
        event_date=event_date,
        title=title,
        category=raw.get("announcementType") or raw.get("announcement_type"),
        source="cninfo",
        url=url,
        summary=raw.get("announcementContent") or raw.get("summary"),
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
        raw=raw,
    )


def normalize_price_daily(ticker: str, raw: dict[str, Any]) -> PriceDaily:
    normalized = normalize_ticker_input(ticker)
    trade_date = normalize_date(raw.get("日期") or raw.get("trade_date")) or ""
    return PriceDaily(
        ticker=normalized,
        trade_date=trade_date,
        open=to_float(raw.get("开盘") or raw.get("open")),
        high=to_float(raw.get("最高") or raw.get("high")),
        low=to_float(raw.get("最低") or raw.get("low")),
        close=to_float(raw.get("收盘") or raw.get("close")),
        volume=to_float(raw.get("成交量") or raw.get("volume")),
        amount=to_float(raw.get("成交额") or raw.get("amount")),
        change_pct=to_float(raw.get("涨跌幅") or raw.get("change_pct")),
        turnover_rate=to_float(raw.get("换手率") or raw.get("turnover_rate")),
        source=str(raw.get("source") or "akshare"),
        raw=raw,
    )


def extract_candidate_ticker(text: str) -> str | None:
    match = re.search(r"\b(?:SH|SZ|BJ)?\d{6}(?:\.(?:SH|SZ|BJ))?\b", text.upper())
    if not match:
        return None
    return normalize_ticker_input(match.group(0))
