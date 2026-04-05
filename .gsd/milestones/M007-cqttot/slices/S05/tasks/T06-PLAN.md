---
estimated_steps: 9
estimated_files: 7
skills_used: []
---

# T06: Implement D037: adapter-owned auth readiness checks

Move auth readiness ownership to the provider adapter boundary. Doctor should consume provider-owned auth readiness results. Auth wording must stay truthful: 'auth cache present' not 'logged in'. Improve local readiness quality: file existence + non-empty content. Parseable JSON for JSON auth files.

Steps:
1. Read current check_provider_auth in doctor/checks
2. Add auth_check() method to AgentProvider protocol returning AuthReadiness
3. Implement in ClaudeAgentProvider and CodexAgentProvider
4. Update doctor check to consume adapter-owned result
5. Ensure truthful wording
6. Add tests for both providers, edge cases (empty file, missing file, corrupt file)
7. Run full test suite

## Inputs

- `D037 decision text`
- `current doctor environment checks`
- `current AgentProvider protocol`

## Expected Output

- `AgentProvider.auth_check() protocol method`
- `Adapter implementations`
- `Doctor uses adapter results`
- `Truthful wording tests`

## Verification

uv run pytest tests/adapters/test_claude_agent_provider.py tests/adapters/test_codex_agent_provider.py tests/doctor/ -v && uv run ruff check && uv run mypy src/scc_cli
