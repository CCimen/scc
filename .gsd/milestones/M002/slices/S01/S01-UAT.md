# S01: Live launch-path adoption of AgentProvider and AgentLaunchSpec — UAT

**Milestone:** M002
**Written:** 2026-04-03T19:07:00.564Z

# S01: Live launch-path adoption of AgentProvider and AgentLaunchSpec — UAT

**Milestone:** M002
**Written:** 2026-04-03

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: this slice changed typed internal launch contracts, bootstrap wiring, and launch orchestration behavior. The strongest proof is the targeted characterization and integration tests that exercise those paths directly, plus the full lint/type/test gate.

## Preconditions

- Work from the synced implementation root at `scc-sync-1.7.3/.gsd/worktrees/M002`.
- Python dependencies are installed (`uv sync` already completed for the worktree).
- No local edits are required before running the commands below.

## Smoke Test

Run:

```bash
uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -q
```

Expected: all seam and contract tests pass; in this slice verification run the command passed with `19 passed` and no failures.

## Test Cases

### 1. Bootstrap exposes a live provider seam

1. Run:
   ```bash
   uv run pytest tests/test_bootstrap.py -q
   ```
2. Confirm `test_get_default_adapters_returns_expected_types` passes.
3. Confirm `test_default_adapters_exposes_agent_provider` passes.
4. **Expected:** the default adapter bundle includes a live `agent_provider`, proving the application layer can obtain the seam through `bootstrap.py` instead of importing provider adapters directly.

### 2. Start-session planning emits a typed launch spec

1. Run:
   ```bash
   uv run pytest tests/test_application_start_session.py -q
   ```
2. Confirm `test_prepared_plan_carries_typed_agent_launch_spec` passes.
3. Confirm `test_start_session_dependencies_accept_agent_provider` passes.
4. **Expected:** `prepare_start_session()` builds a `StartSessionPlan` with a typed `agent_launch_spec`, and the dependency bundle safely accepts the provider seam during live planning.

### 3. Provider-neutral contract guards stay intact

1. Run:
   ```bash
   uv run pytest tests/test_core_contracts.py -q
   ```
2. Confirm the provider-contract tests covering `AgentLaunchSpec`, `ProviderCapabilityProfile`, and `AgentProvider` all pass.
3. Pay special attention to the tests asserting that settings-backed launches store file references in `artifact_paths` and keep `AgentLaunchSpec.env` as a clean `dict[str, str]`.
4. **Expected:** the core contract remains provider-neutral; provider-specific settings encoding does not leak into the shared runtime contract.

### 4. Full regression gate remains green

1. Run:
   ```bash
   uv run ruff check
   ```
2. Run:
   ```bash
   uv run mypy src/scc_cli
   ```
3. Run:
   ```bash
   uv run pytest --tb=short -q
   ```
4. **Expected:** all three commands pass. In the slice completion run, the gate was green with `3249 passed, 23 skipped, 3 xfailed, 1 xpassed` and zero failures.

## Edge Cases

### Backward-compatible dry-run and unwired call paths stay safe

1. Run:
   ```bash
   uv run pytest tests/test_start_dryrun.py -q
   ```
2. **Expected:** dry-run flows still pass without requiring a live provider launch artifact, which matches the slice decision that unwired or dry-run paths return `None` for `agent_launch_spec` rather than crashing callers mid-migration.

## Failure Signals

- `tests/test_bootstrap.py` fails because `DefaultAdapters` no longer exposes `agent_provider`.
- `tests/test_application_start_session.py` fails because `StartSessionPlan` no longer carries `agent_launch_spec` or because dependency wiring regressed.
- `tests/test_core_contracts.py` fails because provider settings leaked into `env` or because the provider contract shape changed incompatibly.
- `ruff` or `mypy` fails after touching `bootstrap.py`, shared dataclasses, or provider-adapter imports.

## Not Proven By This UAT

- It does not prove live launches against external Claude or Codex binaries with real credentials.
- It does not prove pre-launch provider-core destination validation or durable audit persistence; those are intentionally deferred to S04.

## Notes for Tester

If the exact full-suite pass count increases later because adjacent slices land more tests, treat that as acceptable as long as the command remains green with zero failures and the targeted seam tests above still pass. The most trustworthy slice-level signals are the bootstrap, start-session, and core-contract test files named in this UAT.
