---
estimated_steps: 9
estimated_files: 7
skills_used: []
---

# T03: Implement D035: provider-owned settings serialization

Refactor AgentSettings so the runner produces rendered bytes, not a dict. OCI runtime writes bytes verbatim without format assumption. AgentRunner.build_settings() becomes responsible for serialization (JSON for Claude, TOML for Codex).

Steps:
1. Read current AgentSettings model and its consumers
2. Change AgentSettings from content:dict to rendered_bytes:bytes + path:Path + suffix:str
3. Update ClaudeAgentRunner.build_settings() to serialize JSON
4. Update CodexAgentRunner.build_settings() to serialize TOML
5. Update OCI runtime _inject_settings to write rendered_bytes verbatim (remove json.dumps)
6. Add tests proving Claude renders JSON, Codex renders TOML, runtime no longer assumes JSON
7. Run full test suite

## Inputs

- `D035 decision text`
- `current contracts.py AgentSettings`
- `current runner implementations`

## Expected Output

- `AgentSettings with rendered_bytes field`
- `Runners own serialization`
- `OCI runtime format-agnostic`
- `Tests for both formats`

## Verification

uv run pytest tests/adapters/test_claude_agent_runner.py tests/adapters/test_codex_agent_runner.py tests/adapters/test_oci_sandbox_runtime.py -v && uv run ruff check && uv run mypy src/scc_cli
