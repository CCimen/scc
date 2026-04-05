---
estimated_steps: 8
estimated_files: 5
skills_used: []
---

# T02: Implement D041: provider-native config layering for Codex

Implement the config ownership model from D041. Current code builds settings under /home/agent using spec.settings_path. Codex SCC-managed config should use workspace-scoped .codex/config.toml (project-scoped), not home-level provider config. Handle repo cleanliness: ensure .codex is excluded/ignored safely without mutating tracked files unexpectedly. Add tests for repo cleanliness and expected behavior. Claude path (settings.json) should remain as-is.

Steps:
1. Read current _inject_settings and _build_agent_settings in OCI runtime and start_session
2. Update Codex settings path in ProviderRuntimeSpec to use workspace-scoped path
3. Update OCI runtime to handle workspace-scoped vs volume-scoped settings injection
4. Ensure .codex dir in workspace mount does not dirty user repos (add to .gitignore guidance or use ephemeral mount)
5. Add tests proving Codex config goes to workspace mount, Claude config goes to volume
6. Run full test suite

## Inputs

- `D041 decision text`
- `current oci_sandbox_runtime.py`
- `current provider_registry.py`

## Expected Output

- `Updated ProviderRuntimeSpec with correct Codex settings path`
- `OCI runtime handles workspace-scoped injection`
- `Tests for config layering`

## Verification

uv run pytest tests/test_provider_registry.py tests/adapters/test_oci_sandbox_runtime.py -v && uv run ruff check && uv run mypy src/scc_cli
