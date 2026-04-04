# S05: Critical-path coverage elevation

**Goal:** Drive coverage to 100% on critical seams and decision-heavy logic. Close the worst coverage gaps on critical runtime paths. Bring overall coverage meaningfully above 66%.
**Demo:** After this: TBD

## Tasks
- [ ] **T01: Cover the runtime adapter and docker launch path** — 
  - Files: src/scc_cli/adapters/docker_sandbox_runtime.py, src/scc_cli/docker/launch.py, src/scc_cli/docker/credentials.py, src/scc_cli/docker/core.py, tests/test_docker_core.py, tests/fakes/__init__.py
  - Verify: uv run pytest --cov=scc_cli.adapters.docker_sandbox_runtime --cov=scc_cli.docker --cov-report=term-missing --cov-branch; docker_sandbox_runtime >90%, docker/launch >80%, docker/core >95%
- [ ] **T02: Cover control-plane policy merge and launch planning** — 
  - Files: src/scc_cli/application/compute_effective_config.py, src/scc_cli/core/errors.py, src/scc_cli/core/error_mapping.py, tests/test_compute_effective_config.py, tests/test_core_errors.py, tests/test_error_mapping.py
  - Verify: uv run pytest --cov=scc_cli.application.compute_effective_config --cov=scc_cli.core.errors --cov=scc_cli.core.error_mapping --cov-report=term-missing --cov-branch; all three >95%
- [ ] **T03: Cover safety verdict, audit routing, and provider adapters** — 
  - Files: src/scc_cli/adapters/claude_agent_provider.py, src/scc_cli/application/start_session.py, src/scc_cli/core/contracts.py, tests/test_application_start_session.py, tests/test_core_contracts.py
  - Verify: uv run pytest --cov=scc_cli.adapters --cov=scc_cli.application.start_session --cov-report=term-missing --cov-branch
- [ ] **T04: Cover commands and application layers with highest gaps** — 
  - Files: src/scc_cli/commands/reset.py, src/scc_cli/commands/profile.py, src/scc_cli/application/settings/use_cases.py, src/scc_cli/application/dashboard.py
  - Verify: uv run pytest --cov --cov-report=term-missing --cov-branch; overall coverage >80%
