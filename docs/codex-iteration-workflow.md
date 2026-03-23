# Codex Iteration Workflow

## Usage

Use this file as the single source of truth for the current implementation task.

Recommended loop:

1. Ask Codex to read this file before making changes.
2. Ask Codex to implement only the `Current Task` section.
3. After Codex finishes, ask for a review against the `Acceptance Checklist`.
4. Update this file with the next task after review.

Constraints:

- Follow `AGENTS.md`.
- Keep endpoint contracts stable unless a bug fix requires a contract correction.
- Run tests after changes.
- Update snapshots only when the contract intentionally changes.
- Prefer minimal, local fixes over broad refactors.

## Current Task

Fix the stock sync and overview status semantics with minimal necessary changes.

### Scope

1. Fix ticker normalization consistency in `app/scripts/sync_stock.py`
- The sync script currently reads and writes `sync_state` using the raw user input ticker.
- The stock service normalizes public ticker inputs via `normalize_ticker_input()`.
- This can split sync state across keys like `000001` and `000001.SZ`, breaking incremental sync and `/health/sync`.
- Make the sync script use normalized tickers consistently for:
  - incremental sync checks
  - sync state writes
  - result payload output
- Preserve CLI compatibility for raw inputs like `000001,600519`.

2. Fix partial-success sync observability for prices and events
- In multi-source fetches, prices/events can return usable data while one upstream source fails.
- API `data_status` may become `partial`, but `sync_state` is still recorded as a pure success and clears the last error.
- Make `sync_state` preserve enough information so `/health/sync` can reflect degraded-but-usable outcomes.
- Do not change the external API schema.
- Prefer reusing the existing repository sync-state interpretation instead of introducing a separate state model.

3. Fix stale `updated_at` after successful refresh in prices/events
- In `app/services/stock.py`, prices/events can return `data_status.updated_at` from the previous `last_synced_at` even after a successful refresh.
- Make successful refreshes report the current write/update time.
- Do not change cache-hit behavior.

4. Fix derived `risk_flags` status to propagate `partial`
- `_build_risk_flags_status()` currently handles `missing`, `failed`, and `stale`, but not `partial`.
- If any dependent section is `partial`, the derived risk-flags status should not incorrectly report `fresh`.
- Keep the semantics aligned with the rest of the overview rollup behavior.

## Suggested Files

- `app/scripts/sync_stock.py`
- `app/services/stock.py`
- `app/db/sqlite.py`
- `tests/test_sync_stock_script.py`
- `tests/test_stock_service.py`
- `tests/test_stock_api.py`

## Acceptance Checklist

- Sync script uses normalized tickers consistently for sync-state read/write and reporting.
- Incremental sync no longer creates duplicate sync-state records for raw vs normalized ticker forms.
- Prices/events degraded multi-source outcomes remain visible in sync observability.
- Successful prices/events refreshes no longer return stale `data_status.updated_at`.
- Derived `risk_flags` status correctly returns `partial` when an input section is partial.
- Existing endpoint paths and response field names remain unchanged.
- Tests were run.

## Validation

At minimum, try:

```bash
pytest -q
```

If full-suite execution is blocked by missing dependencies or environment issues, explicitly report:

- the command attempted
- the exact failure reason
- any narrower related test command that was attempted

## Review Output Format

When reviewing a Codex implementation against this file, report:

1. Findings first, ordered by severity, with file/line references.
2. Open questions or assumptions.
3. Brief change summary.
4. Test status.

