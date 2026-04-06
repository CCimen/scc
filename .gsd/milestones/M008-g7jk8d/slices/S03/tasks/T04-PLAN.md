---
estimated_steps: 15
estimated_files: 4
skills_used: []
---

# T04: Document residual legacy code, Docker-backed smoke checks, and final verification

**Documentation:**
1. Add a brief comment block at the top of docker/core.py, docker/launch.py, docker/sandbox.py, adapters/docker_sandbox_runtime.py documenting these as the legacy Docker Desktop sandbox path — retained for users who have Docker Desktop with 'docker sandbox run' support, not active for OCI launches.
2. List all residual Docker Desktop code locations for the milestone summary.

**Docker-backed smoke checks (where Docker is available):**
3. If Docker is available in the test environment, run one smoke flow per provider:
   a. Delete the provider image → run through preflight → verify auto-build triggers (interactive)
   b. Verify non-interactive mode fails with the exact build command in the error
   c. Delete the auth volume → run through preflight → verify auth bootstrap triggers
   These are integration-level checks. If Docker is not available, document as manual verification items.

**Final verification gate:**
4. uv run ruff check — clean
5. uv run mypy src/scc_cli — clean
6. uv run pytest -q — >= 4820 passed, zero regressions
7. Summarize all findings ordered by severity, residual risks, and legacy code boundaries
8. If no major findings remain, state that explicitly with a brief change summary

## Inputs

- None specified.

## Expected Output

- `src/scc_cli/docker/core.py`
- `src/scc_cli/docker/launch.py`
- `src/scc_cli/docker/sandbox.py`
- `src/scc_cli/adapters/docker_sandbox_runtime.py`

## Verification

uv run ruff check && uv run mypy src/scc_cli && uv run pytest -q
