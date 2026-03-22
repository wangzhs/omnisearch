# Stock Data Model

Normalized internal datasets:

- `company_profile`
- `event`
- `financial_summary`
- `price_daily`

The default storage backend is SQLite. The repository boundary is intentionally narrow so these normalized models can be moved to PostgreSQL later without changing the API schema.

## company_profile

Primary key:

- `ticker`

Important normalized fields:

- `dedupe_key`
- `source`
- `source_priority`
- `updated_at`

## event

Primary key:

- `event_id`

Explicit dedupe:

- `dedupe_key`

Normalized fields:

- `event_type`
- `importance`
- `sentiment`
- `source_type`
- `raw_title`
- `source`
- `source_priority`

Stable `event_type` taxonomy:

- `financial_report`
- `earnings_forecast`
- `regulatory_action`
- `shareholder_change`
- `capital_operation`
- `asset_restructuring`
- `pledge`
- `general_disclosure`

## financial_summary

Primary key:

- `record_id`

Explicit dedupe:

- `dedupe_key`

Normalized fields:

- `report_date`
- `announcement_date`
- `report_type`
- `source`
- `source_priority`

## price_daily

Primary key:

- `(ticker, trade_date)`

Explicit dedupe:

- `dedupe_key`

Normalized fields:

- `trade_date`
- `change_pct`
- `turnover_rate`
- `source`
- `source_priority`
