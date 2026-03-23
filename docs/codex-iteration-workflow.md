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

Harden `/health/sync` mixed-state observability coverage with minimal necessary changes.

### Scope

1. Tighten `/health/sync` status filtering coverage
- Add focused tests for sync-state filtering and response semantics when rows contain mixed healthy and degraded states.
- Cover at least:
  - `ticker` filtering with normalized input still returning degraded rows
  - partial/degraded sync rows remaining visible in the response
  - mixed success/error metadata staying stable in the payload
- Prefer API-level tests in `tests/test_stock_api.py`.

2. Tighten sync health aggregation checks
- Add or tighten tests for the response shape when multiple dataset sync states exist for a ticker.
- Cover at least:
  - rows with `status=ok` and retained `last_error_message`
  - rows with `status=partial`
  - deterministic row ordering remaining intact

3. Keep sync contract stable
- Do not redesign `/health/sync` response fields.
- Do not change ticker normalization semantics unless fixing a narrow bug.
- Do not churn snapshots unless a contract change is intentional.

4. Keep scope narrow
- Do not broaden generic web research features.
- Focus on observability contract hardening, not feature expansion.

## Suggested Files

- `app/api/routes.py`
- `app/db/sqlite.py`
- `tests/test_stock_api.py`
- `tests/snapshots/`
- `docs/codex-iteration-workflow.md`

## Acceptance Checklist

- `/health/sync` tests cover mixed-state and degraded-row boundary cases.
- Sync observability remains stable for normalized ticker filtering and mixed success/error metadata.
- Snapshots change only if the sync contract intentionally changed.
- Existing sync response field names remain unchanged unless a bug fix requires a narrow correction.
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
