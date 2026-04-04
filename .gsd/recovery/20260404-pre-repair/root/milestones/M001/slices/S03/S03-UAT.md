# S03: Characterization tests for fragile current behavior — UAT

**Milestone:** M001
**Written:** 2026-04-03T15:35:40.448Z

# UAT

1. Review the new and tightened characterization tests:
   - `tests/test_launch_proxy_env.py`
   - `tests/test_config_inheritance.py`
   - `tests/test_network_policy.py`
   - `tests/test_plugin_isolation.py`
2. Confirm they describe current behavior rather than new feature behavior.
3. Run the targeted characterization suites if desired:
   - `uv run pytest tests/test_launch_proxy_env.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py tests/test_context_recording_warning.py`
   - `uv run pytest tests/test_config_inheritance.py tests/test_config_explain.py tests/test_network_policy.py`
   - `uv run pytest tests/test_docker_policy.py tests/test_docker_policy_integration.py tests/test_plugin_isolation.py`
4. Run the full gate:
   - `uv run ruff check`
   - `uv run mypy src/scc_cli`
   - `uv run pytest`
5. Confirm the gate is green and that the newly characterized launch/config/safety behaviors remain intact.

