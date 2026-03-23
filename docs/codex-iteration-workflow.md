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

Harden `/health/sync` and `/company/{ticker}/overview` with minimal necessary changes.

### Scope

1. Fix ticker normalization in `/health/sync`
- `app/api/routes.py` currently forwards the raw optional `ticker` query parameter directly to `repository.list_sync_state()`.
- Sync state is now written with normalized tickers, so `/health/sync?ticker=000001` can miss rows stored under `000001.SZ`.
- Make `/health/sync` normalize ticker filters when a ticker is provided.
- Preserve behavior when `ticker` is omitted.
- Return the normalized ticker value in the response payload when a ticker filter is used.
- Add or update API tests for:
  - `/health/sync?ticker=000001` returning rows for `000001.SZ`
  - omitted ticker still returning all rows

2. Remove duplicate stock dataset loads during overview assembly
- In `app/services/stock.py`, `get_overview_with_debug()` already loads company, financials, prices, and events.
- It then calls `get_risk_flags(ticker, refresh=refresh)`, which reloads financials, prices, and events again through public service methods.
- This causes duplicated repository/upstream work and risks inconsistent section state within a single overview response.
- Refactor overview assembly so risk flags are derived from the already-loaded `financials`, `prices`, and `events`.
- Keep the external response contract unchanged.
- Keep refresh/cache semantics stable from the caller perspective.

3. Avoid repeated overview status recomputation within one response
- `get_overview_with_debug()` currently recomputes `_build_overview_status(...)` more than once for the same inputs.
- Compute the overview rollup once and reuse it in the response payload and debug payload.
- This is a small cleanup, but it should happen as part of the overview hardening change rather than as a standalone refactor.

4. Add focused regression tests for overview load behavior
- Add tests that verify:
  - overview assembly does not reload financials/prices/events a second time just to compute risk flags
  - the overview debug response still exposes the same section structure and rollup status
- Prefer unit/service-level tests over broad integration rewrites.

## Suggested Files

- `app/api/routes.py`
- `app/scripts/sync_stock.py`
- `app/services/stock.py`
- `app/db/sqlite.py`
- `tests/test_stock_api.py`
- `tests/test_stock_service.py`
- `tests/test_sync_stock_script.py`

## Acceptance Checklist

- `/health/sync` normalizes ticker filters consistently with the stock service.
- `/health/sync?ticker=000001` can return sync rows stored under `000001.SZ`.
- Overview assembly does not reload financials/prices/events solely to compute risk flags.
- Overview response contract remains unchanged.
- Overview debug payload still exposes the expected endpoint and sections.
- Rollup status is computed once and reused during overview debug assembly.
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
