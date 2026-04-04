# S01: Live launch-path adoption of AgentProvider and AgentLaunchSpec

**Goal:** Move the actual launch/resume orchestration onto the provider seam introduced in M001.
**Demo:** After this: TBD

## Tasks
- [x] **T01: Added AgentLaunchSpec/AgentProvider typed contracts, seam-boundary xfail tests, and M001 network vocabulary migration; full suite green at 3244 passed / 0 failed** — 
  - Files: src/scc_cli/application/start_session.py, src/scc_cli/application/launch/prepare_launch_plan.py, tests/test_application_start_session.py, tests/test_bootstrap.py, tests/test_core_contracts.py
  - Verify: uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py
- [x] **T02: Fix two ruff lint errors (F401 unused import, I001 unsorted imports) introduced by T01, restoring green lint+type+test baseline** — 
  - Files: src/scc_cli/application/start_session.py, src/scc_cli/application/launch/prepare_launch_plan.py, src/scc_cli/bootstrap.py, src/scc_cli/ports/models.py, src/scc_cli/ports/agent_provider.py
  - Verify: uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py
- [x] **T03: Wired ClaudeAgentProvider into DefaultAdapters and launch path, promoting all 3 S01 xfail seam tests to passing; full suite at 3247 passed / 0 failed** — 
  - Files: src/scc_cli/adapters/docker_sandbox_runtime.py, src/scc_cli/application/start_session.py, src/scc_cli/bootstrap.py, tests/test_application_start_session.py, tests/test_docker_core.py, tests/test_launch_proxy_env.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest
