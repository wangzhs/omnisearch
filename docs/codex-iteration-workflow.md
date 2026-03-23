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

Harden stock event normalization boundary coverage with minimal necessary changes.

### Scope

1. Tighten event title normalization coverage
- Add focused tests for title normalization behavior that directly affects event dedupe.
- Cover at least:
  - punctuation and whitespace variants collapsing to the same normalized title
  - bracket/prefix noise not causing duplicate events across sources
  - normalization staying conservative enough to avoid obviously unrelated titles merging
- Prefer unit-level tests in `tests/test_stock_normalizers.py`.

2. Tighten event dedupe boundary checks
- Add or tighten tests around event dedupe decisions in service/repository paths.
- Cover at least:
  - same-day same-title cross-source events merging predictably
  - higher-priority source still winning after normalization
  - ordering staying deterministic after dedupe

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

- Event normalization tests cover title/dedupe boundary cases.
- Event dedupe remains deterministic and source-priority aware after normalization.
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
