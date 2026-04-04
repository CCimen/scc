---
id: T01
parent: S02
milestone: M006-d622bc
key_files:
  - src/scc_cli/adapters/codex_agent_runner.py
  - src/scc_cli/core/image_contracts.py
  - images/scc-agent-codex/Dockerfile
  - src/scc_cli/bootstrap.py
  - tests/fakes/__init__.py
  - tests/test_codex_agent_runner.py
  - tests/contracts/test_agent_runner_contract.py
key_decisions:
  - Codex settings path is /home/agent/.codex/config.toml
  - Codex argv is bare ["codex"] with no permission-skip flags
  - Parametric contract tests cover all AgentRunner implementations
duration: 
verification_result: passed
completed_at: 2026-04-04T23:32:24.411Z
blocker_discovered: false
---

# T01: Created CodexAgentRunner adapter with codex argv and .codex settings path, added Codex image constants, Dockerfile, and 13 passing tests including parametric contract coverage

**Created CodexAgentRunner adapter with codex argv and .codex settings path, added Codex image constants, Dockerfile, and 13 passing tests including parametric contract coverage**

## What Happened

Created codex_agent_runner.py mirroring the Claude runner pattern with codex-specific settings path (/home/agent/.codex/config.toml), bare ["codex"] argv, and "Codex" describe string. Added SCC_CODEX_IMAGE and SCC_CODEX_IMAGE_REF to image_contracts.py. Created images/scc-agent-codex/Dockerfile installing Node.js 20 + @openai/codex. Wired codex_agent_runner into DefaultAdapters (None default) and build_fake_adapters(). Extended contract tests with parametric TestAgentRunnerContract covering both runners across 4 contract properties.

## Verification

All four verification gates passed: (1) 13 targeted tests pass, (2) ruff check clean, (3) mypy clean on 3 files, (4) full suite 4541 passed, 23 skipped, 2 xfailed, zero regressions.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_codex_agent_runner.py tests/contracts/test_agent_runner_contract.py -v` | 0 | ✅ pass | 1270ms |
| 2 | `uv run ruff check src/scc_cli/adapters/codex_agent_runner.py src/scc_cli/core/image_contracts.py src/scc_cli/bootstrap.py` | 0 | ✅ pass | 11500ms |
| 3 | `uv run mypy src/scc_cli/adapters/codex_agent_runner.py src/scc_cli/core/image_contracts.py src/scc_cli/bootstrap.py` | 0 | ✅ pass | 5900ms |
| 4 | `uv run pytest --rootdir "$PWD" -q` | 0 | ✅ pass | 73540ms |

## Deviations

Import placement of CodexAgentRunner in bootstrap.py was initially out of alphabetical order; ruff I001 caught it and it was fixed before final verification.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/adapters/codex_agent_runner.py`
- `src/scc_cli/core/image_contracts.py`
- `images/scc-agent-codex/Dockerfile`
- `src/scc_cli/bootstrap.py`
- `tests/fakes/__init__.py`
- `tests/test_codex_agent_runner.py`
- `tests/contracts/test_agent_runner_contract.py`
