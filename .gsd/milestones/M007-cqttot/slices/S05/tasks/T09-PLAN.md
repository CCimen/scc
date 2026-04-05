---
estimated_steps: 7
estimated_files: 2
skills_used: []
---

# T09: Implement D039: runtime permission normalization

Build-time Dockerfile permissions are not enough. Runtime launch must normalize mounted provider state permissions. Provider state dir 0700, auth files 0600, uid 1000 ownership. Scoped to provider state/auth paths only.

Steps:
1. Read current OCI runtime launch sequence
2. Add permission normalization step after container creation, before settings injection
3. Use docker exec to set ownership/permissions on provider config dir and auth files
4. Add tests for normalization command construction
5. Run full test suite

## Inputs

- `D039 decision text`
- `current OCI runtime launch`

## Expected Output

- `Permission normalization docker exec commands`
- `Tests for command construction`

## Verification

uv run pytest tests/adapters/test_oci_sandbox_runtime.py -v && uv run ruff check && uv run mypy src/scc_cli
