---
estimated_steps: 36
estimated_files: 4
skills_used: []
---

# T03: Doctor provider image check with build command hint

## Description

D028 constraint 4: for missing provider images, doctor must print the exact build command. Add a `check_provider_image()` doctor check that runs `docker image inspect` for the active provider's image ref and returns a CheckResult with fix_commands on failure.

## Steps

1. Read `src/scc_cli/doctor/checks/environment.py` to understand the existing check pattern (check_docker, check_docker_running, etc). Note how they use subprocess and return CheckResult.
2. Read `src/scc_cli/core/image_contracts.py` to get the exact image ref constants: `SCC_CLAUDE_IMAGE_REF` and `SCC_CODEX_IMAGE_REF`.
3. Read `src/scc_cli/core/provider_resolution.py` to import `get_selected_provider` for resolving the active provider.
4. Create `check_provider_image()` in `src/scc_cli/doctor/checks/environment.py`:
   - Import `get_selected_provider` from config, `SCC_CLAUDE_IMAGE_REF` and `SCC_CODEX_IMAGE_REF` from image_contracts
   - Map provider_id to image_ref: `{"claude": SCC_CLAUDE_IMAGE_REF, "codex": SCC_CODEX_IMAGE_REF}`
   - Resolve active provider via `config.get_selected_provider()`
   - Run `docker image inspect {image_ref}` via subprocess
   - On success: return CheckResult(name="provider_image", passed=True, message=f"{image_ref} found")
   - On failure: return CheckResult(name="provider_image", passed=False, message=f"{image_ref} not found", fix_commands=[f"docker build -t {image_ref} images/scc-agent-{provider_id}/"], fix_hint=f"Build the {provider} agent image", severity=SeverityLevel.WARNING)
   - Use WARNING severity since the image is only needed for `scc start`, not general usage
5. Read `src/scc_cli/doctor/checks/__init__.py`. Export `check_provider_image`.
6. Read `src/scc_cli/doctor/core.py` `run_doctor()`. Add a call to `check_provider_image()` after the Docker checks (it only makes sense to check the image if Docker is working). Wrap in try/except per the support-bundle partial-results pattern.
7. Create `tests/test_doctor_image_check.py`:
   - Test image found → passed=True
   - Test image not found → passed=False with correct fix_commands containing build command
   - Test unknown provider → falls back to claude image ref
   - Test subprocess failure → graceful failure with appropriate message
   - Mock subprocess.run to avoid Docker dependency

## Must-Haves

- [ ] check_provider_image() exists and returns CheckResult
- [ ] On missing image, fix_commands contains exact `docker build -t scc-agent-{provider}:latest images/scc-agent-{provider}/` command
- [ ] Doctor runs the check after Docker checks
- [ ] All code passes ruff, mypy

## Verification

- `uv run pytest tests/test_doctor_image_check.py -v --no-cov` — all tests pass
- `uv run ruff check src/scc_cli/doctor/checks/environment.py src/scc_cli/doctor/core.py` — clean
- `uv run mypy src/scc_cli/doctor/checks/environment.py src/scc_cli/doctor/core.py` — no issues
- `uv run pytest --rootdir "$PWD" -q --no-cov` — zero regressions

## Negative Tests

- **Malformed inputs**: unknown provider_id → falls back to claude image ref
- **Error paths**: subprocess timeout or CalledProcessError → graceful CheckResult(passed=False)
- **Boundary conditions**: Docker not running → check returns failed with helpful message

## Inputs

- ``src/scc_cli/doctor/checks/environment.py` — existing check_docker, check_docker_running patterns`
- ``src/scc_cli/doctor/checks/__init__.py` — existing exports`
- ``src/scc_cli/doctor/core.py` — run_doctor() function`
- ``src/scc_cli/core/image_contracts.py` — SCC_CLAUDE_IMAGE_REF, SCC_CODEX_IMAGE_REF constants`
- ``src/scc_cli/config.py` — get_selected_provider() function`

## Expected Output

- ``src/scc_cli/doctor/checks/environment.py` — check_provider_image() function`
- ``src/scc_cli/doctor/checks/__init__.py` — check_provider_image export`
- ``src/scc_cli/doctor/core.py` — provider image check in run_doctor()`
- ``tests/test_doctor_image_check.py` — image check tests with subprocess mocking`

## Verification

uv run pytest tests/test_doctor_image_check.py -v --no-cov && uv run ruff check src/scc_cli/doctor/checks/environment.py src/scc_cli/doctor/core.py && uv run mypy src/scc_cli/doctor/checks/environment.py src/scc_cli/doctor/core.py && uv run pytest --rootdir "$PWD" -q --no-cov
