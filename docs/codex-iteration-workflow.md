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

Harden overview status and source-metadata helper consistency with minimal necessary changes.

### Scope

1. Tighten overview helper consistency in `StockDataService`
- Review helper methods that construct overview-level `data_status` and section/source metadata.
- Prefer small local fixes that make derived status assembly more consistent across overview sections.
- Cover at least:
  - overview-level status/source selection staying aligned with section statuses
  - source metadata remaining present and shape-stable for derived sections
  - helper behavior not depending on ad hoc route-level shaping

2. Tighten focused service/API coverage around helper-driven behavior
- Add or refine tests that exercise helper output through:
  - service-level overview assembly
  - `GET /company/{ticker}/overview?debug=true`
- Prefer tests that guard status/source metadata consistency rather than broad snapshots.

3. Keep overview contract stable
- Do not redesign overview response fields.
- Do not change endpoint paths.
- Do not broaden debug payload shape unless fixing a narrow inconsistency.

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
- `docs/stock-api.md`
- `docs/codex-iteration-workflow.md`

## Acceptance Checklist

- Overview helper behavior is more internally consistent without expanding the API surface.
- Service/API coverage protects overview status and source-metadata consistency.
- Existing overview field names remain unchanged unless a bug fix requires a narrow correction.
- Existing endpoint paths and response field names remain unchanged.
- Docs change only if observable contract meaning changed.
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
