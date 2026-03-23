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

Harden sync script observability and reporting stability with minimal necessary changes.

### Scope

1. Tighten sync report contract coverage
- `app/scripts/sync_stock.py` now emits richer summary/report fields, including partial outcomes.
- Add focused tests for the sync script report contract so future changes do not silently drift.
- Cover at least:
  - top-level summary counters
  - per-ticker `status` values including `partial`
  - per-dataset entries for `ok`, `failed`, and `skipped`
  - overview section summary content remaining stable

2. Make partial ticker reporting explicit and stable
- Review the final JSON report shape from the sync script.
- Ensure partial outcomes are reported consistently at both:
  - per-ticker result level
  - top-level summary level
- Prefer test and small implementation hardening over broad refactors.

3. Keep sync contract narrow and stable
- Do not redesign the sync script CLI.
- Do not change existing stock endpoint paths.
- Do not broaden generic web research features.
- Keep scope limited to observability/report stability unless a small supporting fix is required.

## Suggested Files

- `app/scripts/sync_stock.py`
- `tests/test_sync_stock_script.py`
- `docs/codex-iteration-workflow.md`

## Acceptance Checklist

- Sync script report tests cover partial and mixed-outcome scenarios.
- Per-ticker and top-level summary reporting remain stable.
- Existing CLI flags and report field names remain unchanged unless a bug fix requires a narrow correction.
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
