# S04: Error handling, exception taxonomy, and audit robustness

**Goal:** Make error handling explicit, consistent, and robust across CLI, JSON, and audit surfaces. Eliminate all 27 bare except+pass sites, harden all subprocess calls, freeze all mutable global state, and ensure fail-closed behavior on security/policy paths.
**Demo:** After this slice, every error path produces consistent output across human, JSON, and audit surfaces. No silent error swallowing. No mutable security defaults. No unhandled subprocess failures.

## Tasks
- [ ] **T01: Eliminate all silent error swallowing** — Fix all 27 bare `except Exception: pass` sites that silently swallow errors. Priority targets: application/dashboard.py (8 sites), ui/dashboard/orchestrator.py (10+ sites), docker/credentials.py (4 sites), application/settings/use_cases.py (3 sites), core/personal_profiles.py (1 site), maintenance/ (6 sites), update.py (1 site), utils/ttl.py (1 site), ui/picker.py (1 site), commands/launch/flow.py (1 site). For each: either add logging, convert to domain-specific exception, use result-object pattern, or add explicit justification comment if the swallow is intentional.
  - Estimate: medium
  - Files: src/scc_cli/application/dashboard.py, src/scc_cli/ui/dashboard/orchestrator.py, src/scc_cli/docker/credentials.py, src/scc_cli/application/settings/use_cases.py, src/scc_cli/core/personal_profiles.py, src/scc_cli/maintenance/*.py, src/scc_cli/update.py, src/scc_cli/utils/ttl.py, src/scc_cli/ui/picker.py, src/scc_cli/commands/launch/flow.py
  - Verify: grep -rn "except.*:\s*$" src/scc_cli followed by grep for "pass" shows zero silent swallows without justification; uv run pytest passes

- [ ] **T02: Harden subprocess handling** — Fix all 4 CRITICAL subprocess.run sites with no error handling: config.py:340 (editor launch — add FileNotFoundError catch), ui/git_interactive.py:869 (git hooks — check returncode), ui/git_interactive.py:600 (git branch -D — check returncode before showing success), commands/worktree/worktree_commands.py:613 (add OSError/PermissionError handling). Fix all HIGH sites where returncode is not checked after calls where failure matters. Ensure all subprocess calls either use check=True or explicitly test returncode.
  - Estimate: small
  - Files: src/scc_cli/config.py, src/scc_cli/ui/git_interactive.py, src/scc_cli/commands/worktree/worktree_commands.py, src/scc_cli/marketplace/materialize.py, src/scc_cli/marketplace/team_fetch.py, src/scc_cli/ui/dashboard/orchestrator.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest

- [ ] **T03: Freeze mutable global state and security defaults** — Fix docker/launch.py:41 DEFAULT_SAFETY_NET_POLICY (public mutable dict for security default — make Final or factory function). Fix all other mutable module-level state: maintenance/tasks.py:136 _TASK_REGISTRY, application/settings/use_cases.py:76 SETTINGS_ACTIONS (make tuple), update.py:59 _PRERELEASE_ORDER, core/network_policy.py:9 _NETWORK_POLICY_ORDER, ui/help.py:43 _MODE_NAMES. Use Final, frozenset, tuple, or MappingProxyType where appropriate.
  - Estimate: small
  - Files: src/scc_cli/docker/launch.py, src/scc_cli/maintenance/tasks.py, src/scc_cli/application/settings/use_cases.py, src/scc_cli/update.py, src/scc_cli/core/network_policy.py, src/scc_cli/ui/help.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest

- [ ] **T04: Strengthen exception taxonomy and ensure fail-closed behavior** — Review SCCError subclass hierarchy for completeness. Ensure all error paths use domain-specific exceptions (not generic Exception or bare raise). Verify fail-closed behavior on security/policy paths: if safety policy cannot load, if network policy is ambiguous, if provider requirements cannot be validated — the system must fail closed, never default to permissive. Verify error categories, exit codes, and audit event emission are consistent across CLI/JSON/audit surfaces.
  - Estimate: medium
  - Files: src/scc_cli/core/errors.py, src/scc_cli/core/error_mapping.py, src/scc_cli/json_command.py, src/scc_cli/commands/**/*.py, src/scc_cli/application/*.py, src/scc_cli/docker/*.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest

- [ ] **T05: Verify audit event consistency across all error paths** — Ensure that error events flow through the audit sink consistently, with correct category, exit code, and contextual metadata. Add tests for error-path audit emission. Verify that the 10+ ui/dashboard/orchestrator.py sites that print error and return sentinels are fixed to produce structured results callers can distinguish from success.
  - Estimate: small
  - Files: src/scc_cli/core/errors.py, src/scc_cli/ui/dashboard/orchestrator.py, tests/test_core_errors.py, tests/test_error_mapping.py
  - Verify: uv run pytest tests/test_core_errors.py tests/test_error_mapping.py && uv run pytest
