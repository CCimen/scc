---
estimated_steps: 7
estimated_files: 3
skills_used: []
---

# T05: Implement D040: file-based Codex auth in containers

Force cli_auth_credentials_store='file' in the SCC-managed Codex config layer. Ensure auth writes back to the persistent provider volume. Add tests.

Steps:
1. Read current Codex settings construction in CodexAgentRunner or start_session
2. Ensure cli_auth_credentials_store='file' is always set in the Codex config
3. Verify auth.json path is in the persistent volume mount
4. Add tests: presence of file-based auth config, auth persistence path in volume
5. Run full test suite

## Inputs

- `D040 decision text`
- `current Codex runner and start_session`

## Expected Output

- `Codex config includes file-based auth store`
- `Tests for auth config presence`

## Verification

uv run pytest tests/adapters/test_codex_agent_runner.py -v && uv run ruff check && uv run mypy src/scc_cli
