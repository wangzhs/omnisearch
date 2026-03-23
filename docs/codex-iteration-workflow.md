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

Harden schema example stability for stock debug responses with minimal necessary changes.

### Scope

1. Shrink `OverviewDebugResponse` example to a minimal stable contract example
- `app/schemas/stock.py` currently carries a very large hand-written example for `OverviewDebugResponse`.
- This is high-maintenance and likely to drift from implementation details over time.
- Replace it with a shorter example that demonstrates the contract without encoding too many volatile field values.
- Keep the example useful for readers of the OpenAPI schema.
- The example should show structure, not a near-real full payload.
- Keep only the minimum needed to demonstrate:
  - `ticker`
  - top-level `data_status.status`
  - top-level `source_metadata` shape
  - `debug.endpoint`
  - the 6 overview debug section keys
  - at least one section-level `data_status`
- Remove high-drift details such as large business objects, many timestamps, long source arrays, and verbose message strings unless strictly needed.
- Current review note:
  - The latest attempt is still too detailed to pass.
  - It still includes too many fixed timestamps, repeated full `data_status` objects, and detailed message/reason strings.
  - The next revision should cut the example down again until it reads like a contract illustration, not a partial real payload.

2. Add a focused regression test for schema/example drift
- Add a targeted test that validates the stock debug schema example stays aligned with the current contract.
- At minimum, assert:
  - `debug.endpoint` matches the actual overview debug endpoint name
  - the overview debug section keys are present
  - `data_status.status` can represent `partial`
  - the example retains `source_metadata` structure where expected
- Prefer a narrow test over broad schema snapshot churn.
- Keep the test aligned with the smaller example; do not make the test require a large detailed payload.

3. Keep stock contract and docs stable
- Do not change endpoint paths.
- Do not remove existing response fields.
- Do not redesign the stock schemas.
- Keep scope limited to schema/example drift prevention unless a tiny supporting fix is required.

## Suggested Files

- `app/schemas/stock.py`
- `tests/test_stock_api.py`
- `docs/codex-iteration-workflow.md`

## Acceptance Checklist

- `OverviewDebugResponse` example is substantially smaller and easier to keep stable.
- A focused test guards against overview debug schema/example drift.
- `debug.endpoint` and section structure remain aligned with the real response contract.
- The example reads like a stable contract illustration rather than a hand-written full response.
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
