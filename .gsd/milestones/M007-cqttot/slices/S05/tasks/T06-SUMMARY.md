---
id: T06
parent: S05
milestone: M007-cqttot
key_files:
  - src/scc_cli/ports/agent_provider.py
  - src/scc_cli/adapters/claude_agent_provider.py
  - src/scc_cli/adapters/codex_agent_provider.py
  - src/scc_cli/doctor/checks/environment.py
  - tests/fakes/fake_agent_provider.py
  - tests/test_claude_agent_provider.py
  - tests/test_codex_agent_provider.py
  - tests/test_doctor_provider_errors.py
key_decisions:
  - D037 implemented: auth readiness is adapter-owned, doctor consumes AuthReadiness
  - Auth check does file existence + non-empty + parseable JSON (not just file existence)
  - Doctor dispatches to adapter via bootstrap, not direct subprocess calls
duration: 
verification_result: passed
completed_at: 2026-04-05T15:05:26.999Z
blocker_discovered: false
---

# T06: Added auth_check() to AgentProvider protocol; Claude and Codex adapters validate file existence, non-empty content, and parseable JSON; doctor delegates to adapter-owned results with truthful wording

**Added auth_check() to AgentProvider protocol; Claude and Codex adapters validate file existence, non-empty content, and parseable JSON; doctor delegates to adapter-owned results with truthful wording**

## What Happened

Added auth_check() -> AuthReadiness to the AgentProvider protocol. Implemented in both ClaudeAgentProvider (.credentials.json in docker-claude-sandbox-data) and CodexAgentProvider (auth.json in docker-codex-sandbox-data) with three-tier validation: volume existence, file content retrieval via docker cat, and parseable JSON validation. Rewired doctor check_provider_auth to resolve the adapter via bootstrap and call auth_check(), replacing inline Docker subprocess logic. Ensured truthful wording: 'auth cache present' not 'logged in'. Updated FakeAgentProvider for protocol compliance. Added 14 adapter-level tests and rewrote 10 doctor-level tests.

## Verification

ruff check: zero errors. mypy: zero issues in 293 files. Targeted tests (46 passed). Truthfulness/branding tests (41 passed). Full suite: 4760 passed, 0 failed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 8000ms |
| 2 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 3 | `uv run pytest tests/test_claude_agent_provider.py tests/test_codex_agent_provider.py tests/test_doctor_provider_errors.py -v` | 0 | ✅ pass | 4000ms |
| 4 | `uv run pytest tests/test_docs_truthfulness.py tests/test_provider_branding.py -v` | 0 | ✅ pass | 1000ms |
| 5 | `uv run pytest -q` | 0 | ✅ pass | 55000ms |

## Deviations

Test file paths adjusted from plan (tests/adapters/ and tests/doctor/ → tests/ root). Auth check reads file content via docker cat instead of test -f, enabling non-empty and JSON validation in a single subprocess call.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/ports/agent_provider.py`
- `src/scc_cli/adapters/claude_agent_provider.py`
- `src/scc_cli/adapters/codex_agent_provider.py`
- `src/scc_cli/doctor/checks/environment.py`
- `tests/fakes/fake_agent_provider.py`
- `tests/test_claude_agent_provider.py`
- `tests/test_codex_agent_provider.py`
- `tests/test_doctor_provider_errors.py`
