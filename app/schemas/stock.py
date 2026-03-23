from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EventType = Literal[
    "financial_report",
    "earnings_forecast",
    "regulatory_action",
    "shareholder_change",
    "capital_operation",
    "asset_restructuring",
    "pledge",
    "general_disclosure",
]


class CompanyProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker: str
    name: str | None = None
    exchange: str | None = None
    market: str | None = None
    industry: str | None = None
    area: str | None = None
    list_date: str | None = None
    status: str | None = None
    website: str | None = None
    chairman: str | None = None
    manager: str | None = None
    employees: int | None = None
    main_business: str | None = None
    business_scope: str | None = None
    source: str
    source_priority: int | None = None
    updated_at: str | None = None


class SourceMetadata(BaseModel):
    selected_source: str | None = None
    selected_source_priority: int | None = None
    fallback_used: bool = False
    attempted_sources: list[str] = Field(default_factory=list)
    returned_sources: list[str] = Field(default_factory=list)
    selection_reason: str | None = None
    fallback_reason: str | None = None


class DataStatus(BaseModel):
    status: Literal["fresh", "partial", "stale", "missing", "failed"]
    updated_at: str | None = None
    source: str | None = None
    ttl_hours: int
    cache_hit: bool = False
    error_message: str | None = None
    last_synced_at: str | None = None
    last_success_at: str | None = None
    last_error_at: str | None = None
    last_error_message: str | None = None
    source_metadata: SourceMetadata | None = None


class Event(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    ticker: str
    dedupe_key: str | None = None
    event_date: str | None = None
    title: str
    raw_title: str | None = None
    event_type: EventType | None = None
    category: str | None = None
    sentiment: Literal["positive", "neutral", "negative"] | None = None
    source_type: Literal["filing", "exchange_search", "news", "derived"] | None = None
    source: str
    source_priority: int | None = None
    url: str | None = None
    source_url: str | None = None
    summary: str | None = None
    updated_at: str | None = None
    importance: Literal["high", "medium", "low"] | None = None


class FinancialSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    record_id: str
    ticker: str
    report_date: str
    announcement_date: str | None = None
    report_type: str | None = None
    revenue: float | None = None
    revenue_yoy: float | None = None
    net_profit: float | None = None
    net_profit_yoy: float | None = None
    eps: float | None = None
    roe: float | None = None
    gross_margin: float | None = None
    source: str
    source_priority: int | None = None
    updated_at: str | None = None


class PriceDaily(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker: str
    trade_date: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: float | None = None
    amount: float | None = None
    change_pct: float | None = None
    turnover_rate: float | None = None
    source: str
    source_priority: int | None = None
    updated_at: str | None = None


class RiskFlag(BaseModel):
    level: str
    code: str
    message: str
    dimension: str | None = None
    as_of_date: str | None = None


class CompanyOverviewCompanySection(BaseModel):
    data: CompanyProfile | None = None
    data_status: DataStatus


class CompanyOverviewFinancialSection(BaseModel):
    data: FinancialSummary | None = None
    data_status: DataStatus


class CompanyOverviewPriceSection(BaseModel):
    data: PriceDaily | None = None
    data_status: DataStatus


class CompanyOverviewEventsSection(BaseModel):
    data: list[Event] = Field(default_factory=list)
    data_status: DataStatus


class CompanyOverviewRiskFlagsSection(BaseModel):
    data: list[RiskFlag] = Field(default_factory=list)
    data_status: DataStatus


class OverviewSignal(BaseModel):
    code: str
    label: str
    value: str
    importance: Literal["high", "medium", "low"]
    direction: Literal["positive", "neutral", "negative"]
    evidence: str | None = None


class CompanyOverviewSignalsSection(BaseModel):
    data: list[OverviewSignal] = Field(default_factory=list)
    data_status: DataStatus


class CompanyOverview(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "ticker": "000001.SZ",
                "company": {
                    "data": {
                        "ticker": "000001.SZ",
                        "name": "Ping An Bank",
                        "exchange": "SZSE",
                        "market": "Main Board",
                        "industry": "Bank",
                        "area": "Guangdong",
                        "list_date": "1991-04-03",
                        "status": "L",
                        "website": "https://bank.pingan.com",
                        "chairman": None,
                        "manager": None,
                        "employees": None,
                        "main_business": None,
                        "business_scope": None,
                        "source": "tushare",
                        "source_priority": 100,
                        "updated_at": "2026-03-17T00:00:00Z",
                    },
                    "data_status": {
                        "status": "fresh",
                        "updated_at": "2026-03-17T00:00:00Z",
                        "source": "tushare",
                        "ttl_hours": 24,
                        "cache_hit": True,
                        "error_message": None,
                        "last_synced_at": "2026-03-17T00:00:00Z",
                        "last_success_at": "2026-03-17T00:00:00Z",
                        "last_error_at": None,
                        "last_error_message": None,
                        "source_metadata": {"selected_source": "tushare", "selected_source_priority": 100, "fallback_used": False, "attempted_sources": ["tushare"]},
                    },
                },
                "latest_financial": {
                    "data": {
                        "record_id": "000001.SZ:2025-12-31:annual",
                        "ticker": "000001.SZ",
                        "report_date": "2025-12-31",
                        "announcement_date": "2026-03-16",
                        "report_type": "annual",
                        "revenue": 100.0,
                        "revenue_yoy": -2.0,
                        "net_profit": -5.0,
                        "net_profit_yoy": -10.0,
                        "eps": 0.2,
                        "roe": 1.0,
                        "gross_margin": 30.0,
                        "source": "tushare",
                        "source_priority": 100,
                        "updated_at": "2026-03-17T00:00:00Z",
                    },
                    "data_status": {
                        "status": "fresh",
                        "updated_at": "2026-03-17T00:00:00Z",
                        "source": "tushare",
                        "ttl_hours": 24,
                        "cache_hit": True,
                        "error_message": None,
                        "last_synced_at": "2026-03-17T00:00:00Z",
                        "last_success_at": "2026-03-17T00:00:00Z",
                        "last_error_at": None,
                        "last_error_message": None,
                        "source_metadata": {"selected_source": "tushare", "selected_source_priority": 100, "fallback_used": False, "attempted_sources": ["tushare"]},
                    },
                },
                "latest_price": {
                    "data": {
                        "ticker": "000001.SZ",
                        "trade_date": "2026-03-13",
                        "open": 10.0,
                        "high": 11.0,
                        "low": 9.9,
                        "close": 10.8,
                        "volume": 1000.0,
                        "amount": 5000.0,
                        "change_pct": 9.5,
                        "turnover_rate": 2.0,
                        "source": "akshare",
                        "source_priority": 90,
                        "updated_at": "2026-03-17T00:00:00Z",
                    },
                    "data_status": {
                        "status": "fresh",
                        "updated_at": "2026-03-17T00:00:00Z",
                        "source": "akshare",
                        "ttl_hours": 24,
                        "cache_hit": True,
                        "error_message": None,
                        "last_synced_at": "2026-03-17T00:00:00Z",
                        "last_success_at": "2026-03-17T00:00:00Z",
                        "last_error_at": None,
                        "last_error_message": None,
                        "source_metadata": {"selected_source": "akshare", "selected_source_priority": 90, "fallback_used": False, "attempted_sources": ["akshare", "tushare"]},
                    },
                },
                "recent_events": {
                    "data": [
                        {
                            "event_id": "evt-1",
                            "ticker": "000001.SZ",
                            "dedupe_key": "evt-1",
                            "event_date": "2026-03-16",
                            "title": "Annual report disclosed",
                            "raw_title": "Annual report disclosed",
                            "event_type": "financial_report",
                            "category": "report",
                            "sentiment": "neutral",
                            "source_type": "filing",
                            "source": "cninfo",
                            "source_priority": 100,
                            "url": "https://example.com/report.pdf",
                            "source_url": "https://example.com/report.pdf",
                            "summary": "Annual report filing",
                            "updated_at": "2026-03-17T00:00:00Z",
                            "importance": "high",
                        }
                    ],
                    "data_status": {
                        "status": "fresh",
                        "updated_at": "2026-03-17T00:00:00Z",
                        "source": "cninfo",
                        "ttl_hours": 24,
                        "cache_hit": True,
                        "error_message": None,
                        "last_synced_at": "2026-03-17T00:00:00Z",
                        "last_success_at": "2026-03-17T00:00:00Z",
                        "last_error_at": None,
                        "last_error_message": None,
                        "source_metadata": {"selected_source": "cninfo", "selected_source_priority": 100, "fallback_used": False, "attempted_sources": ["cninfo", "exchange_search"]},
                    },
                },
                "risk_flags": {
                    "data": [
                        {
                            "level": "high",
                            "code": "negative_net_profit",
                            "message": "Latest reported net profit is negative.",
                            "dimension": "financial",
                            "as_of_date": "2026-03-16",
                        }
                    ],
                    "data_status": {
                        "status": "fresh",
                        "updated_at": "2026-03-17T00:00:00Z",
                        "source": "derived",
                        "ttl_hours": 24,
                        "cache_hit": True,
                        "error_message": None,
                        "last_synced_at": "2026-03-17T00:00:00Z",
                        "last_success_at": "2026-03-17T00:00:00Z",
                        "last_error_at": None,
                        "last_error_message": None,
                        "source_metadata": {"selected_source": "derived", "selected_source_priority": 0, "fallback_used": False, "attempted_sources": ["derived"]},
                    },
                },
                "signals": {
                    "data": [
                        {
                            "code": "profitability",
                            "label": "Profitability",
                            "value": "negative",
                            "importance": "high",
                            "direction": "negative",
                            "evidence": "Latest reported net profit is below zero.",
                        }
                    ],
                    "data_status": {
                        "status": "fresh",
                        "updated_at": "2026-03-17T00:00:00Z",
                        "source": "derived",
                        "ttl_hours": 24,
                        "cache_hit": True,
                        "error_message": None,
                        "last_synced_at": "2026-03-17T00:00:00Z",
                        "last_success_at": "2026-03-17T00:00:00Z",
                        "last_error_at": None,
                        "last_error_message": None,
                        "source_metadata": {"selected_source": "derived", "selected_source_priority": 0, "fallback_used": False, "attempted_sources": ["derived"]},
                    },
                },
            }
        }
    )

    ticker: str
    company: CompanyOverviewCompanySection
    latest_financial: CompanyOverviewFinancialSection
    latest_price: CompanyOverviewPriceSection
    recent_events: CompanyOverviewEventsSection
    risk_flags: CompanyOverviewRiskFlagsSection
    signals: CompanyOverviewSignalsSection


class PriceSourceDebug(BaseModel):
    source: str
    status: str
    count: int = 0
    kept_count: int = 0
    error: str | None = None


class StockPaginationDebug(BaseModel):
    limit: int | None = None
    page: int | None = None
    page_size: int | None = None
    returned_items: int = 0
    total_items: int = 0
    sort_by: str | None = None
    sort_order: str | None = None


class StockSectionDebug(BaseModel):
    data_status: DataStatus
    sources: list[PriceSourceDebug] = Field(default_factory=list)


class StockEndpointDebug(BaseModel):
    endpoint: str
    sources: list[PriceSourceDebug] = Field(default_factory=list)
    pagination: StockPaginationDebug | None = None
    sections: dict[str, StockSectionDebug] = Field(default_factory=dict)


class PriceListDebugResponse(BaseModel):
    ticker: str
    items: list[PriceDaily] = Field(default_factory=list)
    data_status: DataStatus
    debug: StockEndpointDebug


class EventSourceDebug(PriceSourceDebug):
    pass


class EventListDebugResponse(BaseModel):
    ticker: str
    items: list[Event] = Field(default_factory=list)
    data_status: DataStatus
    debug: StockEndpointDebug


class CompanyDebugResponse(BaseModel):
    ticker: str
    data: CompanyProfile | None = None
    data_status: DataStatus
    debug: StockEndpointDebug


class FinancialListDebugResponse(BaseModel):
    ticker: str
    items: list[FinancialSummary] = Field(default_factory=list)
    data_status: DataStatus
    debug: StockEndpointDebug


class OverviewDebugResponse(BaseModel):
    ticker: str
    data: CompanyOverview
    data_status: DataStatus
    debug: StockEndpointDebug


class TimelineItem(BaseModel):
    date: str
    kind: str
    title: str
    summary: str | None = None
    url: str | None = None
    source: str
    importance: Literal["high", "medium", "low"] | None = None


class StockResearchContext(BaseModel):
    ticker: str
    company: CompanyProfile
    recent_events: list[Event] = Field(default_factory=list)
    latest_financial: FinancialSummary | None = None
    latest_price: PriceDaily | None = None
    risk_flags: list[RiskFlag] = Field(default_factory=list)
