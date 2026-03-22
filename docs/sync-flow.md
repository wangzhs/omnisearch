# Sync Flow

The sync entrypoint is `python -m app.scripts.sync_stock`.

## Modes

- full: sync selected datasets immediately
- incremental: skip datasets whose local sync state is still within TTL
- dry-run: print the planned dataset work without upstream calls

## Dataset Order

- `company`
- `financials`
- `prices`
- `events`
- `overview`

`overview` is assembled after raw datasets so the output reflects current local state.

## Retry

Each dataset call supports:

- `--retries`
- `--retry-backoff-seconds`

Backoff uses exponential growth from the base delay.

## Reporting

The script prints a JSON report containing:

- `generated_at`
- `mode`
- `selected_datasets`
- `results`
- `failure_count`
- `failures`

Optional file output:

- `--json-report report.json`
