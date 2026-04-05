---
id: T05
parent: S05
milestone: M007-cqttot
key_files:
  - src/scc_cli/adapters/codex_agent_runner.py
  - tests/test_codex_agent_runner.py
key_decisions:
  - D040 implemented in CodexAgentRunner.build_settings() via _SCC_MANAGED_DEFAULTS dict merged under caller config
duration: 
verification_result: passed
completed_at: 2026-04-05T14:55:19.199Z
blocker_discovered: false
---

# T05: CodexAgentRunner now always injects cli_auth_credentials_store='file' into Codex config for reliable container auth persistence

**CodexAgentRunner now always injects cli_auth_credentials_store='file' into Codex config for reliable container auth persistence**

## What Happened

Implemented D040 by adding _SCC_MANAGED_DEFAULTS class attribute to CodexAgentRunner containing cli_auth_credentials_store='file'. In build_settings(), these defaults merge under caller config so SCC keys are always present but governed config can override. Auth.json persists in the docker-codex-sandbox-data volume at /home/agent/.codex/auth.json. Added 4 tests in TestD040FileBasedAuth covering empty config, caller preservation, explicit override precedence, and volume path verification.

## Verification

uv run pytest tests/test_codex_agent_runner.py -v — 11 passed. uv run ruff check — zero errors. uv run mypy src/scc_cli — 0 issues. uv run pytest tests/test_docs_truthfulness.py tests/test_provider_branding.py -v — 41 passed. uv run pytest -q — 4745 passed, 0 failed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_codex_agent_runner.py -v` | 0 | ✅ pass | 5600ms |
| 2 | `uv run ruff check` | 0 | ✅ pass | 5600ms |
| 3 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 5600ms |
| 4 | `uv run pytest tests/test_docs_truthfulness.py tests/test_provider_branding.py -v` | 0 | ✅ pass | 5800ms |
| 5 | `uv run pytest -q` | 0 | ✅ pass | 52700ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/adapters/codex_agent_runner.py`
- `tests/test_codex_agent_runner.py`
