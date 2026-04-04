# S05: Critical-path coverage elevation

**Goal:** Drive coverage to 100% on critical seams and decision-heavy logic. Close the worst coverage gaps on critical runtime paths. Bring overall coverage meaningfully above 66%.
**Demo:** After this slice, all critical decision paths have exhaustive meaningful coverage including branch coverage on policy-heavy and failure-sensitive code. The runtime adapter is no longer at 22%.

## Tasks
- [ ] **T01: Cover the runtime adapter and docker launch path** — adapters/docker_sandbox_runtime.py is at 22% (the main runtime adapter — the worst critical-seam gap). docker/launch.py is at 54% with 105 statements uncovered (lines 397-512 and 834-879 entirely uncovered). docker/credentials.py is at 8%. Add comprehensive tests covering container lifecycle, network setup, credential mounting, and error paths. Use fakes/mocks for Docker where needed but prefer the existing fake infrastructure in tests/fakes/.
  - Estimate: large
  - Files: src/scc_cli/adapters/docker_sandbox_runtime.py, src/scc_cli/docker/launch.py, src/scc_cli/docker/credentials.py, src/scc_cli/docker/core.py, tests/test_docker_core.py, tests/fakes/__init__.py
  - Verify: uv run pytest --cov=scc_cli.adapters.docker_sandbox_runtime --cov=scc_cli.docker --cov-report=term-missing --cov-branch; docker_sandbox_runtime >90%, docker/launch >80%, docker/core >95%

- [ ] **T02: Cover control-plane policy merge and launch planning** — application/compute_effective_config.py is at 90% (lines 458-505, 549-605, 709-730 uncovered — likely edge cases in policy merge). core/error_mapping.py is at 74% (6 statements missing). core/errors.py is at 86% (12 statements in exception raise paths). Add exhaustive tests for config inheritance, policy merge (org/team widening, project/user narrowing), error classification, and exit mapping. Include edge cases and failure paths.
  - Estimate: medium
  - Files: src/scc_cli/application/compute_effective_config.py, src/scc_cli/core/errors.py, src/scc_cli/core/error_mapping.py, tests/test_compute_effective_config.py, tests/test_core_errors.py, tests/test_error_mapping.py
  - Verify: uv run pytest --cov=scc_cli.application.compute_effective_config --cov=scc_cli.core.errors --cov=scc_cli.core.error_mapping --cov-report=term-missing --cov-branch; all three >95%

- [ ] **T03: Cover safety verdict, audit routing, and provider adapters** — Add tests for safety engine evaluation, audit event emission/routing, and provider adapter behavior. Cover fail-closed behavior when safety policy cannot load. Test both Claude and Codex adapter paths. Cover application/start_session.py remaining 4% gap.
  - Estimate: medium
  - Files: src/scc_cli/adapters/claude_agent_provider.py, src/scc_cli/application/start_session.py, src/scc_cli/core/contracts.py, tests/test_application_start_session.py, tests/test_core_contracts.py
  - Verify: uv run pytest --cov=scc_cli.adapters --cov=scc_cli.application.start_session --cov-report=term-missing --cov-branch

- [ ] **T04: Cover commands and application layers with highest gaps** — commands/reset.py (7%), commands/profile.py (9%), application/settings/use_cases.py (36%), application/dashboard.py (where untested). These are not critical seams but represent the largest absolute coverage holes. Add focused tests covering the main user-facing paths and error handling.
  - Estimate: medium
  - Files: src/scc_cli/commands/reset.py, src/scc_cli/commands/profile.py, src/scc_cli/application/settings/use_cases.py, src/scc_cli/application/dashboard.py
  - Verify: uv run pytest --cov --cov-report=term-missing --cov-branch; overall coverage >80%
