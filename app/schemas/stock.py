from pydantic import BaseModel, ConfigDict, Field


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
    updated_at: str | None = None


class Event(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    ticker: str
    event_date: str | None = None
    title: str
    category: str | None = None
    source: str
    url: str | None = None
    summary: str | None = None
    updated_at: str | None = None
    importance: str | None = None


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
    updated_at: str | None = None


class RiskFlag(BaseModel):
    level: str
    code: str
    message: str
    dimension: str | None = None
    as_of_date: str | None = None


class CompanyOverview(BaseModel):
    company: CompanyProfile
    latest_financial: FinancialSummary | None = None
    latest_price: PriceDaily | None = None
    recent_events: list[Event] = Field(default_factory=list)
    risk_flags: list[RiskFlag] = Field(default_factory=list)


class PriceSourceDebug(BaseModel):
    source: str
    status: str
    count: int = 0
    error: str | None = None


class PriceListDebugResponse(BaseModel):
    ticker: str
    items: list[PriceDaily] = Field(default_factory=list)
    debug: list[PriceSourceDebug] = Field(default_factory=list)


class EventSourceDebug(BaseModel):
    source: str
    status: str
    count: int = 0
    kept_count: int = 0
    error: str | None = None


class EventListDebugResponse(BaseModel):
    ticker: str
    items: list[Event] = Field(default_factory=list)
    debug: list[EventSourceDebug] = Field(default_factory=list)


class TimelineItem(BaseModel):
    date: str
    kind: str
    title: str
    summary: str | None = None
    url: str | None = None
    source: str
    importance: str | None = None


class StockResearchContext(BaseModel):
    ticker: str
    company: CompanyProfile
    recent_events: list[Event] = Field(default_factory=list)
    latest_financial: FinancialSummary | None = None
    latest_price: PriceDaily | None = None
    risk_flags: list[RiskFlag] = Field(default_factory=list)
