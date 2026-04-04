# S03: Strict typing hardening (Pyright + mypy)

**Goal:** Raise Pyright and mypy to strict mode on `src/scc_cli` with only narrow, documented, justified exceptions. Replace the ~200+ `dict[str, Any]` config/policy pipeline with typed models. Make `InteractionRequest.value` generic. Eliminate all untyped definitions from the maintained source tree.
**Demo:** After this slice, `uv run pyright src/scc_cli` and `uv run mypy src/scc_cli` pass in strict mode with minimal documented carve-outs, and the config pipeline uses typed models end-to-end.

## Tasks
- [ ] **T01: Introduce typed config/policy models to replace dict[str, Any]** — This is the root cause of most typing issues. Create Pydantic or TypedDict models for: org config, team config, project config, user config, effective merged config, network policy config, safety policy config, and provider config. Replace the ~200+ `dict[str, Any]` function parameters/returns across the config/policy pipeline with these typed models. Start from core/ and ports/, then propagate outward to application/ and commands/. The existing `UserConfig: TypeAlias = dict[str, Any]` in flow.py must become a real typed model.
  - Estimate: large
  - Files: src/scc_cli/core/personal_profiles.py, src/scc_cli/application/compute_effective_config.py, src/scc_cli/commands/launch/flow.py, src/scc_cli/claude_adapter.py, src/scc_cli/teams.py, src/scc_cli/commands/team.py, src/scc_cli/docker/launch.py, src/scc_cli/remote.py, src/scc_cli/config.py, src/scc_cli/ports/personal_profile_service.py, src/scc_cli/adapters/personal_profile_service_local.py
  - Verify: grep -r "dict\[str, Any\]" src/scc_cli | wc -l shows substantial reduction; uv run mypy src/scc_cli passes

- [ ] **T02: Make InteractionRequest generic and eliminate cast() abuse** — The 44 cast() calls (15 in flow.py, 12 in wizard.py) exist because `InteractionRequest.value` is untyped. Make it generic `InteractionRequest[T]` with typed value field. Fix all 4 `dict[Any, Any]` casts (validate.py, config.py, docker/launch.py, sessions.py) to use `dict[str, Any]` or proper typed models. Remove or justify every remaining cast() call.
  - Estimate: medium
  - Files: src/scc_cli/application/interaction_requests.py, src/scc_cli/commands/launch/flow.py, src/scc_cli/ui/wizard.py, src/scc_cli/validate.py, src/scc_cli/config.py, src/scc_cli/docker/launch.py, src/scc_cli/sessions.py
  - Verify: grep -r "cast(" src/scc_cli | wc -l shows substantial reduction; uv run pyright src/scc_cli passes

- [ ] **T03: Fix core contracts and models for strict typing** — Push strict Pyright and mypy through core/*.py and ports/*.py first. These must pass with zero suppressions. Fix all missing return type annotations (339 total across codebase — start with core/ and ports/).
  - Estimate: medium
  - Files: src/scc_cli/core/*.py, src/scc_cli/ports/*.py
  - Verify: uv run pyright src/scc_cli/core src/scc_cli/ports && uv run mypy src/scc_cli/core src/scc_cli/ports — zero errors, zero suppressions

- [ ] **T04: Fix application, adapters, and service layers for strict typing** — Extend strict typing to application/, adapters/, services/, and evaluation/. Fix all `Any` parameters, untyped defs, and implicit optional types. Address the 4 `type: ignore` comments (config.py:21, audit/reader.py:64, json_command.py:134, ui/picker.py:752) — fix the underlying type issue or add justification.
  - Estimate: medium
  - Files: src/scc_cli/application/**/*.py, src/scc_cli/adapters/*.py, src/scc_cli/services/**/*.py, src/scc_cli/evaluation/*.py
  - Verify: uv run pyright src/scc_cli && uv run mypy src/scc_cli passes

- [ ] **T05: Fix remaining modules and remove all transitional mypy/pyright relaxations** — Address remaining strict-mode issues in CLI entry points, docker/, marketplace/, doctor/, commands/, and ui/. Remove all transitional mypy overrides from pyproject.toml (implicit_reexport for scc_cli.git/ui.wizard/ui.dashboard.models, disallow_untyped_calls for maintenance.migrations). Enable warn_unreachable and fix the 19 unreachable statements. Enable redundant-cast checking and fix the 2 redundant casts. Document any narrow remaining suppressions with justification comments.
  - Estimate: medium
  - Files: src/scc_cli/cli.py, src/scc_cli/docker/*.py, src/scc_cli/marketplace/*.py, src/scc_cli/doctor/*.py, src/scc_cli/commands/**/*.py, src/scc_cli/ui/**/*.py, pyproject.toml
  - Verify: uv run pyright src/scc_cli && uv run mypy src/scc_cli && uv run ruff check && uv run pytest; pyproject.toml has no transitional mypy overrides remaining
