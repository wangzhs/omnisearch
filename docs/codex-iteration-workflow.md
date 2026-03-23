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

Harden stock event dedupe fallback behavior with minimal necessary changes.

### Scope

1. Tighten dedupe fallback coverage for incomplete source data
- Add focused tests for cases where event inputs are incomplete but still need deterministic dedupe behavior.
- Cover at least:
  - empty or punctuation-only titles falling back to URL-sensitive dedupe behavior
  - missing `event_date` still producing stable keys for obviously identical source records
  - dedupe not over-merging unrelated URL-only records
- Prefer unit-level tests in `tests/test_stock_normalizers.py`.

2. Tighten service-level dedupe boundary checks
- Add or tighten tests around dedupe decisions when normalized titles are empty or event dates are missing.
- Cover at least:
  - same-source duplicate records with incomplete titles collapsing predictably
  - cross-source incomplete records not over-merging unless the remaining signals really match
  - deterministic ordering remaining intact after fallback dedupe

3. Keep event contract stable
- Do not redesign event response fields or event type taxonomy.
- Do not churn snapshots unless a contract change is intentional.

4. Keep scope narrow
- Do not broaden generic web research features.
- Focus on normalization hardening, not feature expansion.

## Suggested Files

- `app/normalizers/stock.py`
- `app/services/stock.py`
- `tests/test_stock_normalizers.py`
- `tests/test_stock_service.py`
- `tests/snapshots/`
- `docs/codex-iteration-workflow.md`

## Acceptance Checklist

- Event normalization tests cover incomplete-input and fallback-dedupe boundary cases.
- Event dedupe remains deterministic and source-priority aware when titles or dates are incomplete.
- Snapshots change only if the event contract intentionally changed.
- Existing event field names remain unchanged unless a bug fix requires a narrow correction.
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
