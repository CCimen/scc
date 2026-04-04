# S03: Typed config model adoption and strict typing cleanup

**Goal:** Raise Pyright and mypy to strict mode on `src/scc_cli` with only narrow, documented, justified exceptions. Replace the ~200+ `dict[str, Any]` config/policy pipeline with typed models. Make `InteractionRequest.value` generic. Eliminate all untyped definitions from the maintained source tree.
**Demo:** After this: TBD

## Tasks
- [ ] **T01: Introduce typed config/policy models to replace dict[str, Any]** — 
  - Files: src/scc_cli/core/personal_profiles.py, src/scc_cli/application/compute_effective_config.py, src/scc_cli/commands/launch/flow.py, src/scc_cli/claude_adapter.py, src/scc_cli/teams.py, src/scc_cli/commands/team.py, src/scc_cli/docker/launch.py, src/scc_cli/remote.py, src/scc_cli/config.py, src/scc_cli/ports/personal_profile_service.py, src/scc_cli/adapters/personal_profile_service_local.py
  - Verify: grep -r "dict\[str, Any\]" src/scc_cli | wc -l shows substantial reduction; uv run mypy src/scc_cli passes
- [ ] **T02: Make InteractionRequest generic and eliminate cast() abuse** — 
  - Files: src/scc_cli/application/interaction_requests.py, src/scc_cli/commands/launch/flow.py, src/scc_cli/ui/wizard.py, src/scc_cli/validate.py, src/scc_cli/config.py, src/scc_cli/docker/launch.py, src/scc_cli/sessions.py
  - Verify: grep -r "cast(" src/scc_cli | wc -l shows substantial reduction; uv run pyright src/scc_cli passes
- [ ] **T03: Fix core contracts and models for strict typing** — 
  - Files: src/scc_cli/core/*.py, src/scc_cli/ports/*.py
  - Verify: uv run pyright src/scc_cli/core src/scc_cli/ports && uv run mypy src/scc_cli/core src/scc_cli/ports — zero errors, zero suppressions
- [ ] **T04: Fix application, adapters, and service layers for strict typing** — 
  - Files: src/scc_cli/application/**/*.py, src/scc_cli/adapters/*.py, src/scc_cli/services/**/*.py, src/scc_cli/evaluation/*.py
  - Verify: uv run pyright src/scc_cli && uv run mypy src/scc_cli passes
- [ ] **T05: Fix remaining modules and remove all transitional mypy/pyright relaxations** — 
  - Files: src/scc_cli/cli.py, src/scc_cli/docker/*.py, src/scc_cli/marketplace/*.py, src/scc_cli/doctor/*.py, src/scc_cli/commands/**/*.py, src/scc_cli/ui/**/*.py, pyproject.toml
  - Verify: uv run pyright src/scc_cli && uv run mypy src/scc_cli && uv run ruff check && uv run pytest; pyproject.toml has no transitional mypy overrides remaining
