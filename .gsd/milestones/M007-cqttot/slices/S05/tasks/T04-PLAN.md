---
estimated_steps: 7
estimated_files: 2
skills_used: []
---

# T04: Implement D033: Codex launch policy argv

Current CodexAgentRunner still launches plain `codex`. D033 says launch with `codex --dangerously-bypass-approvals-and-sandbox` inside the SCC container. Implement or explicitly revise D033 if a different policy is correct. Keep runner-owned.

Steps:
1. Read current CodexAgentRunner.build_command()
2. Update build_command to include --dangerously-bypass-approvals-and-sandbox
3. Add tests proving the flag is present in command output
4. Verify existing tests still pass
5. Run full test suite

## Inputs

- `D033 decision text`
- `current CodexAgentRunner`

## Expected Output

- `CodexAgentRunner includes bypass flag`
- `Tests verify flag presence`

## Verification

uv run pytest tests/adapters/test_codex_agent_runner.py -v && uv run ruff check && uv run mypy src/scc_cli
