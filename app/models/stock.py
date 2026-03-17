from pydantic import BaseModel, Field


class CompanyProfile(BaseModel):
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
    raw: dict = Field(default_factory=dict)


class Event(BaseModel):
    event_id: str
    ticker: str
    event_date: str | None = None
    title: str
    category: str | None = None
    source: str
    url: str | None = None
    summary: str | None = None
    importance: str | None = None
    updated_at: str | None = None
    raw: dict = Field(default_factory=dict)


class FinancialSummary(BaseModel):
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
    raw: dict = Field(default_factory=dict)


class PriceDaily(BaseModel):
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
    raw: dict = Field(default_factory=dict)
