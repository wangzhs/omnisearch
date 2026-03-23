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

- `status`: `fresh | partial | stale | missing | failed`
- `updated_at`
- `source`
- `ttl_hours`
- `cache_hit`
- `error_message`
- `last_synced_at`
- `last_success_at`
- `last_error_at`
- `last_error_message`
- `source_metadata`

Status semantics:

- `fresh`: local data is present and still within TTL
- `partial`: usable data was produced, but at least one upstream source errored or degraded during refresh
- `stale`: local data is present but older than TTL
- `missing`: no usable local or upstream data is available
- `failed`: refresh failed and no usable result could be produced for that section

`source_metadata` explains runtime source selection:

- `selected_source`
- `selected_source_priority`
- `fallback_used`
- `attempted_sources`
- `returned_sources`
- `selection_reason`
- `fallback_reason`

## Supporting Endpoints

- `GET /company/{ticker}`
- `GET /company/{ticker}/events`
- `GET /company/{ticker}/financials`
- `GET /company/{ticker}/prices`
- `GET /company/{ticker}/timeline`
- `GET /company/{ticker}/risk-flags`

## Debug-Capable Endpoints

The following stock endpoints support `debug=true` and return a stable observability envelope with:

- `ticker`
- `data_status`
- `debug.endpoint`
- `debug.sources`
- `debug.pagination` when pagination applies

Endpoints:

- `GET /company/{ticker}?debug=true`
- `GET /company/{ticker}/overview?debug=true`
- `GET /company/{ticker}/events?debug=true`
- `GET /company/{ticker}/financials?debug=true`
- `GET /company/{ticker}/prices?debug=true`

`GET /company/{ticker}/overview?debug=true` is the main stock observability entrypoint. In addition to top-level `data_status`, it returns `debug.sections` for:

- `company`
- `latest_financial`
- `latest_price`
- `recent_events`
- `risk_flags`
- `signals`

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
- `debug=true`
- `report_type`
- `sort_by=report_date|announcement_date|revenue|net_profit`
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

### `GET /health/sources`

Reports upstream configuration state without probing live connectivity. Current response shape:

- `status`
- `summary`
- `sources.tushare.configured`
- `sources.tushare.base_url`
- `sources.cninfo.configured`
- `sources.cninfo.url`
- `sources.akshare.configured`

`summary` fields:

- `status`
- `total_sources`
- `configured_count`
- `unconfigured_count`

`status` / `summary.status` semantics:

- top-level `status`: endpoint health only; remains `ok` when the endpoint can report configuration state
- `summary.status = ok`: all declared upstream sources are configured
- `summary.status = partial`: at least one declared upstream source is currently unconfigured

### `GET /health/sync`

Returns repository sync-state rows. Optional `ticker` is normalized to the canonical A-share ticker format before filtering.

Top-level response shape:

- `status`
- `ticker`
- `summary`
- `items`

`summary` fields:

- `status`
- `ok_count`
- `partial_count`
- `failed_count`
- `latest_degraded_dataset`

`summary.status` semantics:

- `failed`: at least one sync row is `failed`
- `partial`: no row failed, but at least one sync row is `partial`
- `ok`: all returned rows are `ok`

Each item can include:

- `dataset`
- `ticker`
- `status`
- `synced_at`
- `last_synced_at`
- `last_success_at`
- `last_error_at`
- `last_error_message`
- `records_written`
- `duration_ms`

`status` may be `ok`, `partial`, or `failed` depending on the last recorded sync outcome.
`latest_degraded_dataset` names the most recent `partial` or `failed` dataset when one exists.
