# Stock API

OmniSearch treats A-share stock data as the primary product surface.

## Primary Contract

`GET /company/{ticker}/overview`

Returns a stable sectioned response:

- `ticker`
- `company`
- `latest_financial`
- `latest_price`
- `recent_events`
- `risk_flags`
- `signals`

Each section contains:

- `data`
- `data_status`

`data_status` fields:

- `status`: `fresh | stale | missing | failed`
- `updated_at`
- `source`
- `ttl_hours`
- `cache_hit`
- `error_message`

Status semantics:

- `fresh`: local data is present and still within TTL
- `stale`: local data is present but older than TTL
- `missing`: no usable local or upstream data is available
- `failed`: refresh failed and no usable result could be produced for that section

## Supporting Endpoints

- `GET /company/{ticker}`
- `GET /company/{ticker}/events`
- `GET /company/{ticker}/financials`
- `GET /company/{ticker}/prices`
- `GET /company/{ticker}/timeline`
- `GET /company/{ticker}/risk-flags`

## Filters and Pagination

### Events

Supported query params:

- `limit`
- `refresh`
- `debug=true`
- `event_type`
- `importance`
- `source`
- `sentiment`
- `sort_by=event_date|importance|updated_at`
- `sort_order=asc|desc`
- `page`
- `page_size`

### Financials

Supported query params:

- `limit`
- `refresh`
- `report_type`
- `sort_order=asc|desc`
- `page`
- `page_size`

### Prices

Supported query params:

- `limit`
- `start_date`
- `end_date`
- `refresh`
- `debug=true`
- `min_change_pct`
- `max_change_pct`
- `sort_order=asc|desc`
- `page`
- `page_size`

## Health Endpoints

- `GET /health`
- `GET /health/db`
- `GET /health/sources`
- `GET /health/sync`
