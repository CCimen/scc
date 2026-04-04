# S03: Codex adapter as a first-class provider on the same seam — UAT

**Milestone:** M002
**Written:** 2026-04-03T19:40:08.377Z

# S03: Codex adapter as a first-class provider on the same seam — UAT

**Milestone:** M002
**Written:** 2026-04-03

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: this slice ships a provider adapter, contract tests, and composition-root wiring rather than a new end-user runtime surface, so the most truthful proof is targeted tests plus repo-gate verification.

## Preconditions

- Run from the M002 worktree root.
- Dependencies are synced (`uv sync`).
- Use `./tests/...` when invoking focused pytest files from the worktree so pytest resolves paths against the worktree instead of the synced repo root.

## Smoke Test

Run `uv run pytest ./tests/test_codex_agent_provider.py -q`.

Expected: `4 passed`, proving the Codex adapter exposes its metadata and clean launch-spec shape.

## Test Cases

### 1. Codex adapter reports honest provider metadata and clean launch specs

1. Run `uv run pytest ./tests/test_codex_agent_provider.py -q`.
2. Confirm the suite covers four behaviors: capability metadata, launch without settings, launch with one settings artifact, and env string-safety.
3. **Expected:** all four tests pass; `provider_id` is `codex`, `required_destination_set` is `openai-core`, `argv` is `('codex',)`, `env` stays empty, and a provided settings path appears only in `artifact_paths`.

### 2. The shared seam still composes through bootstrap without adapter import leakage

1. Run `uv run pytest tests/test_bootstrap.py tests/test_import_boundaries.py tests/test_application_start_session.py tests/test_core_contracts.py tests/test_cli.py tests/test_integration.py -q`.
2. Inspect the pass result for `tests/test_import_boundaries.py` to confirm only `bootstrap.py` imports `scc_cli.adapters.*`.
3. **Expected:** the focused seam/bootstrap suite passes (`96 passed` in the verified run), proving `DefaultAdapters` can carry both Claude and Codex providers while higher layers stay provider-neutral.

### 3. Static typing and repo gates still pass after introducing Codex as a second real provider

1. Run `uv run pyright src/scc_cli/adapters/codex_agent_provider.py tests/test_codex_agent_provider.py`.
2. Run `uv run ruff check`.
3. Run `uv run mypy src/scc_cli`.
4. Run `uv run pytest --tb=short -q`.
5. **Expected:** pyright reports `0 errors, 0 warnings`, lint passes, mypy succeeds, and the full repo suite stays green (`3249 passed, 23 skipped, 3 xfailed, 1 xpassed` in the verified run).

## Edge Cases

### Absent or present settings artifact path

1. In `tests/test_codex_agent_provider.py`, verify both `settings_path=None` and `settings_path=<path>` cases are exercised.
2. **Expected:** `artifact_paths` is empty when no settings artifact exists, contains exactly the provided path when one exists, and `env` remains `{}` in both cases.

## Failure Signals

- `tests/test_codex_agent_provider.py` fails on metadata drift, nested env data, or accidental Codex-specific fields leaking into shared contracts.
- `tests/test_import_boundaries.py` fails because non-bootstrap modules import from `scc_cli.adapters.*`.
- `pyright`, `mypy`, or the full pytest gate fail after Codex wiring, indicating the second provider broke the seam or a construction site was missed.

## Not Proven By This UAT

- A live Codex runtime launch inside the sandbox.
- Pre-launch destination validation, durable audit persistence, or any Codex resume/skills/native-integration behavior.

## Notes for Tester

This slice intentionally proves architecture, not end-user interaction. If a future slice adds real Codex launch selection or provider-specific UX, extend UAT from contract-level proof to a live launch-path test rather than loosening the current adapter boundary.
