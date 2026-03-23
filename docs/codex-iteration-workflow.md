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

Refine derived status `selection_reason` semantics with minimal necessary changes.

### Scope

1. Tighten derived helper `selection_reason` semantics
- Review the derived status helpers in `StockDataService`.
- Replace overly broad or misleading `selection_reason` values with narrower helper-specific values where appropriate.
- Cover at least:
  - overview-level derived status metadata
  - `risk_flags` derived status metadata
  - `signals` or other derived sections that rely on the same helper path

2. Tighten focused service/API coverage around derived metadata semantics
- Add or refine tests that exercise helper output through:
  - service-level overview assembly
  - `GET /company/{ticker}/overview?debug=true`
- Prefer tests that guard `selection_reason` correctness and metadata stability rather than broad snapshots.

3. Keep overview contract stable
- Do not redesign overview response fields.
- Do not change endpoint paths.
- Do not broaden debug payload shape unless fixing a narrow inconsistency.
- Do not change status rollup semantics as part of this task.

4. Update docs only if contract meaning changes
- If helper changes alter observable overview semantics, update `docs/stock-api.md`.
- Otherwise avoid doc churn.

5. Keep scope narrow
- Do not broaden generic web research features.
- Focus on internal consistency hardening, not feature expansion.

## Suggested Files

- `app/services/stock.py`
- `app/schemas/stock.py`
- `tests/test_stock_service.py`
- `tests/test_stock_api.py`
- `docs/codex-iteration-workflow.md`

## Acceptance Checklist

- Derived `selection_reason` values are narrower and internally consistent.
- Service/API coverage protects derived metadata semantics without changing status behavior.
- Existing overview field names remain unchanged unless a bug fix requires a narrow correction.
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
