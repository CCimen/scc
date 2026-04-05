---
estimated_steps: 7
estimated_files: 4
skills_used: []
---

# T08: Implement D038/D042: config freshness on every fresh launch

On every fresh launch (not resume), SCC writes the SCC-managed config layer deterministically — even when logically empty. On resume, existing config is left in place. Scoped to SCC-owned config layers only.

Steps:
1. Read current OCI runtime fresh-launch vs resume paths
2. Ensure fresh launch always writes the SCC-managed config (even if empty/default)
3. Ensure resume does NOT overwrite config
4. Add tests: governed->standalone, teamA->teamB, settings->no-settings transitions
5. Run full test suite

## Inputs

- `D038 and D042 decision text`
- `current OCI runtime settings injection`

## Expected Output

- `Deterministic config write on fresh launch`
- `No overwrite on resume`
- `Transition tests`

## Verification

uv run pytest tests/adapters/test_oci_sandbox_runtime.py tests/commands/launch/ -v && uv run ruff check && uv run mypy src/scc_cli
