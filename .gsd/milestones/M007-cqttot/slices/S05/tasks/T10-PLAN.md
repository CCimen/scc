---
estimated_steps: 8
estimated_files: 3
skills_used: []
---

# T10: Image hardening: scc-base and scc-agent-codex improvements

scc-base should prepare both ~/.claude and ~/.codex with correct ownership/permissions. scc-agent-codex should pin Codex package version via ARG. Keep builds deterministic.

Steps:
1. Read current Dockerfile definitions in images/
2. Update scc-base to create both .claude and .codex dirs with 0700/uid1000
3. Update scc-agent-codex to use ARG for version pinning
4. Ensure doctor/build guidance matches actual image tags and build commands
5. Add integration tests for structural properties
6. Run test suite

## Inputs

- `D036 and D039 decision text`
- `current Dockerfiles`

## Expected Output

- `Updated Dockerfiles`
- `Structural tests`

## Verification

uv run pytest tests/test_image_structure.py -v && uv run ruff check
