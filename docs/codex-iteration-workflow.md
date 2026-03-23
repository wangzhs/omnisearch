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

Stabilize `/health/sync` summary contract with explicit schema and documentation updates.

### Scope

1. Add an explicit response schema for `/health/sync`
- Move the route away from an untyped `dict` response for this endpoint.
- Add schema models for:
  - sync row item
  - sync summary
  - sync response
- Cover at least:
  - `summary.status`
  - `ok_count`
  - `partial_count`
  - `failed_count`
  - `latest_degraded_dataset`

2. Update stock API documentation for `/health/sync`
- Document the new `summary` object in `docs/stock-api.md`.
- Keep the documented semantics narrow and aligned with the implementation.

3. Tighten API/schema coverage for the summary contract
- Add focused API tests for `/health/sync`.
- Cover at least:
  - response still serializes the same `items`
  - `summary` shape matches the schema contract
  - normalized ticker filtering still works

4. Keep sync contract stable
- Do not redesign existing `/health/sync` row fields.
- Do not remove or rename `items`.
- Keep the current summary semantics unchanged unless a narrow correction is required.
- Do not change ticker normalization semantics unless fixing a narrow bug.
- Do not churn snapshots unless a contract change is intentional.

5. Keep scope narrow
- Do not broaden generic web research features.
- Focus on observability value, not feature expansion.

## Suggested Files

- `app/api/routes.py`
- `app/schemas/stock.py`
- `docs/stock-api.md`
- `tests/test_stock_api.py`
- `tests/snapshots/`
- `docs/codex-iteration-workflow.md`

## Acceptance Checklist

- `/health/sync` has an explicit response schema.
- Documentation reflects the current `summary` contract.
- Existing `items` ordering and row fields remain unchanged.
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
