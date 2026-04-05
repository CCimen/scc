---
id: T03
parent: S05
milestone: M007-cqttot
key_files:
  - src/scc_cli/ports/models.py
  - src/scc_cli/adapters/claude_agent_runner.py
  - src/scc_cli/adapters/codex_agent_runner.py
  - src/scc_cli/adapters/oci_sandbox_runtime.py
  - src/scc_cli/adapters/docker_sandbox_runtime.py
  - src/scc_cli/application/start_session.py
  - tests/test_claude_agent_runner.py
  - tests/test_codex_agent_runner.py
  - tests/test_oci_sandbox_runtime.py
key_decisions:
  - Minimal _serialize_toml in codex_agent_runner.py instead of adding tomli_w dependency
  - Pass empty dict to prepare_launch config param since providers ignore it
  - Legacy DockerSandboxRuntime deserializes rendered_bytes back to dict for backward compat
duration: 
verification_result: passed
completed_at: 2026-04-05T14:46:43.977Z
blocker_discovered: false
---

# T03: Refactored AgentSettings from content:dict to rendered_bytes:bytes so runners own serialization and OCI runtime writes bytes verbatim

**Refactored AgentSettings from content:dict to rendered_bytes:bytes so runners own serialization and OCI runtime writes bytes verbatim**

## What Happened

Changed AgentSettings in ports/models.py from content: dict[str, Any] + path: Path to rendered_bytes: bytes + path: Path + suffix: str. ClaudeAgentRunner.build_settings() now serializes config to JSON bytes. CodexAgentRunner.build_settings() serializes to TOML bytes via a minimal _serialize_toml() helper. The OCI runtime's _inject_settings() writes rendered_bytes verbatim with the correct file suffix — no more json.dumps(). The legacy DockerSandboxRuntime deserializes bytes back to dict for backward compatibility. Updated _build_agent_launch_spec to pass empty dict to prepare_launch since providers don't consume the config content. Updated all test construction sites, created test_claude_agent_runner.py, and extended Codex runner tests with TOML round-trip verification.

## Verification

uv run ruff check — zero errors. uv run mypy src/scc_cli — 0 issues in 293 files. uv run pytest targeted tests — 106 passed. uv run pytest truthfulness/branding — 41 passed. uv run pytest -q — 4740 passed, 23 skipped, 2 xfailed, 0 failed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 4500ms |
| 2 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4500ms |
| 3 | `uv run pytest tests/test_claude_agent_runner.py tests/test_codex_agent_runner.py tests/test_oci_sandbox_runtime.py tests/contracts/test_agent_runner_contract.py tests/test_application_start_session.py -v` | 0 | ✅ pass | 5600ms |
| 4 | `uv run pytest tests/test_docs_truthfulness.py tests/test_provider_branding.py -v` | 0 | ✅ pass | 3900ms |
| 5 | `uv run pytest -q` | 0 | ✅ pass | 57400ms |

## Deviations

Added _serialize_toml helper in codex_agent_runner.py instead of adding tomli_w dependency. Legacy DockerSandboxRuntime deserializes rendered_bytes back to dict via json.loads. _build_agent_launch_spec passes config={} to prepare_launch since providers ignore it.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/ports/models.py`
- `src/scc_cli/adapters/claude_agent_runner.py`
- `src/scc_cli/adapters/codex_agent_runner.py`
- `src/scc_cli/adapters/oci_sandbox_runtime.py`
- `src/scc_cli/adapters/docker_sandbox_runtime.py`
- `src/scc_cli/application/start_session.py`
- `tests/test_claude_agent_runner.py`
- `tests/test_codex_agent_runner.py`
- `tests/test_oci_sandbox_runtime.py`
