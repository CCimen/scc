---
estimated_steps: 8
estimated_files: 4
skills_used: []
---

# T07: Remove remaining active-launch Claude fallbacks (D032)

Check and eliminate any remaining launch/runtime paths that still substitute Claude when provider wiring is missing or unknown. Active launch logic must not silently choose Claude if agent_provider is absent or provider identity is invalid. Missing provider wiring should surface a typed launch error.

Steps:
1. Search codebase for Claude fallback patterns in launch/runtime paths
2. Identify any silent substitutions (default='claude' in active logic, not read/migration boundaries)
3. Replace with typed errors (InvalidProviderError or ProviderNotReadyError)
4. Preserve read/migration defaults (SessionRecord, config read) per D032
5. Add tests for fail-closed behavior on missing/invalid provider
6. Run full test suite

## Inputs

- `D032 decision text`
- `current launch and runtime code`

## Expected Output

- `No silent Claude fallbacks in active launch logic`
- `Tests for fail-closed dispatch`

## Verification

uv run pytest tests/commands/launch/ tests/adapters/test_oci_sandbox_runtime.py -v && uv run ruff check && uv run mypy src/scc_cli
