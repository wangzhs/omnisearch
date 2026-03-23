# Codex Iteration Workflow

## Usage

Use this file as the single source of truth for the current implementation phase.

Recommended loop:

1. Ask Codex to read this file before making changes.
2. Ask Codex to complete the whole `Current Phase`.
3. After Codex finishes, ask for a review against the `Phase Exit Criteria`.
4. Do not split the phase into tiny follow-up tasks unless review finds a concrete blocker.

Constraints:

- Follow `AGENTS.md`.
- Keep endpoint contracts stable unless a bug fix requires a contract correction.
- Run tests after changes.
- Update snapshots only when the contract intentionally changes.
- Prefer minimal, local fixes over broad refactors.

## Current Phase

Complete `Stock Reliability and Freshness`.

This phase is not done until all workstreams below are complete together.

### Workstream 1: Freshness Correctness

Harden freshness and stale semantics across stock endpoints.

Requirements:

- Review `updated_at`, `last_synced_at`, and stale derivation paths.
- Ensure freshly refreshed data does not present stale metadata.
- Ensure cache-hit vs refresh paths produce coherent freshness fields.
- Prefer small fixes in service/repository logic over broad redesign.

### Workstream 2: Sync Recovery Semantics

Harden degraded and recovery behavior across:

- sync script
- service layer
- repository sync state
- `/health/sync`

Requirements:

- Make recovery after prior errors semantically clear.
- Keep `ok / partial / failed / stale` coherent when upstreams flap.
- Preserve useful last-error context without making status ambiguous.

### Workstream 3: Source Provenance Clarity

Harden source/debug explainability for overview and supporting endpoints.

Requirements:

- Keep `source_metadata` precise and stable.
- Avoid derived/source provenance drift between top-level and section-level responses.
- Keep debug payloads explainable without widening contract scope.

### Workstream 4: Reliability Regression Coverage

Add or tighten focused regression coverage for the reliability behaviors above.

Requirements:

- Prefer targeted service/API tests over broad snapshot churn.
- Run full suite when phase work is complete.
- Keep docs/schema updates limited to observable meaning changes.

## Suggested Files

- `app/api/routes.py`
- `app/services/stock.py`
- `app/normalizers/stock.py`
- `app/db/sqlite.py`
- `app/scripts/sync_stock.py`
- `app/schemas/stock.py`
- `docs/stock-api.md`
- `tests/test_stock_api.py`
- `tests/test_stock_service.py`
- `tests/test_stock_normalizers.py`
- `tests/test_sync_stock_script.py`
- `tests/snapshots/`
- `docs/codex-iteration-workflow.md`

## Phase Exit Criteria

The phase is complete only if all of the following are true:

- Freshness fields and stale semantics are internally coherent after refresh and cache-hit flows.
- Sync recovery semantics are aligned across script, service, repository, and health API.
- Source provenance is stable and explainable across overview/debug responses.
- Reliability-sensitive regressions are covered by focused tests.
- Docs and schemas reflect any observable meaning changes.
- Snapshot churn happened only where contract changes were intentional.
- Full relevant tests were run.
- Preferably run full suite:

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
3. Brief phase-completion summary.
4. Test status.

## Codex Report Format

When Codex reports phase completion, it must explicitly separate:

1. What the current uncommitted diff changed in this round.
2. Whether the current repository state, including previously merged work, now satisfies the phase exit criteria.
3. Which test commands were actually run and what the results were.

Do not collapse those into a single sentence like "the phase is done".

Use this structure:

1. `This round changed`
- List only the files/behaviors changed in the current worktree or current round.

2. `Phase status`
- State either:
  - `Current diff alone does not complete the phase`, or
  - `Current repository state now satisfies the phase exit criteria`
- If claiming the phase is complete, make clear whether that conclusion depends on previously merged commits.

3. `Tests run`
- List the exact commands actually run.
- List the observed results.
