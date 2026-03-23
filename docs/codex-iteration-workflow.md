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

Harden health endpoint observability shape consistency with minimal necessary changes.

### Scope

1. Tighten `/health/sources` and `/health/sync` top-level shape consistency
- Review the top-level payload shape of both health endpoints.
- Prefer small, backward-compatible changes that make their observability structure easier to consume together.
- Cover at least:
  - stable top-level `status`
  - presence or absence of a top-level summary/metadata block
  - source/configuration visibility staying explicit

2. Tighten focused API coverage around health observability semantics
- Add or refine tests for:
  - `GET /health/sources`
  - `GET /health/sync`
- Prefer tests that protect shape consistency and backward compatibility over broad snapshots.

3. Keep health contracts stable
- Do not redesign existing health row fields.
- Do not change endpoint paths.
- Do not remove existing fields from `/health/sources` or `/health/sync`.
- Add only narrow compatibility-safe structure if needed.

4. Update docs only if contract meaning changes
- If the observable health payload meaning changes, update `docs/stock-api.md`.
- Otherwise avoid doc churn.

5. Keep scope narrow
- Do not broaden generic web research features.
- Focus on health observability consistency, not feature expansion.

## Suggested Files

- `app/api/routes.py`
- `app/schemas/stock.py`
- `tests/test_stock_api.py`
- `docs/stock-api.md`
- `docs/codex-iteration-workflow.md`

## Acceptance Checklist

- Health endpoint top-level shapes are more internally consistent without breaking current fields.
- API coverage protects health observability semantics and backward compatibility.
- Existing health field names remain unchanged unless a bug fix requires a narrow correction.
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
