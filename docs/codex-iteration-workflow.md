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

Harden event normalization and event-list stability with minimal necessary changes.

### Scope

1. Harden cross-source event dedupe
- `cninfo` and `exchange_search` can describe the same disclosure with different URLs.
- Current dedupe keys depend on normalized URL, which makes cross-source dedupe fragile and can keep duplicate event rows when the title/date are the same but URLs differ.
- Improve event dedupe so semantically identical events from different sources are more likely to collapse to one normalized event.
- Preserve source-priority selection semantics: when duplicates collapse, the higher-priority source should still win.
- Keep the stable `event_type` taxonomy unchanged.

2. Tighten event ordering stability
- Event ordering currently relies on a mix of `event_date`, `importance`, and `updated_at`.
- Make the ordering deterministic for events with equal dates and equal priority, so pagination and snapshots do not depend on incidental insertion order.
- Do not redesign the endpoint or add new sort fields.

3. Expand normalization coverage with focused tests
- Add regression tests for:
  - duplicate same-day events from different sources collapsing to one event
  - higher-priority source winning when duplicate candidates differ in normalized fields
  - deterministic ordering for same-date events
  - event normalization preserving expected taxonomy and importance semantics
- Prefer unit/service-level tests and only add API coverage where it proves endpoint stability.

4. Keep repository and API contracts stable
- Do not change `/company/{ticker}/events` response fields.
- Do not change the stable event taxonomy documented in `docs/stock-data-model.md`.
- Do not broaden generic web research features while doing this work.

## Suggested Files

- `app/normalizers/stock.py`
- `app/services/stock.py`
- `app/collectors/exchange_search.py`
- `app/services/stock.py`
- `tests/test_stock_normalizers.py`
- `tests/test_stock_service.py`
- `tests/test_stock_api.py`
- `docs/stock-data-model.md`

## Acceptance Checklist

- Cross-source duplicate events are normalized more consistently.
- Higher-priority sources still win after dedupe.
- Event ordering is deterministic for same-date items.
- `/company/{ticker}/events` contract remains unchanged.
- Existing event taxonomy remains unchanged.
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
