---
id: T04
parent: S02
milestone: M003
key_files:
  - src/scc_cli/bootstrap.py
  - src/scc_cli/application/start_session.py
  - tests/test_bootstrap_backend_selection.py
  - tests/test_start_session_image_routing.py
  - tests/test_bootstrap.py
key_decisions:
  - Updated existing test_bootstrap.py to accept either runtime type since probe result is environment-dependent
  - runtime_info threaded as optional field on StartSessionDependencies rather than adding probe call inside start_session
duration: 
verification_result: passed
completed_at: 2026-04-04T09:20:05.877Z
blocker_discovered: false
---

# T04: Wire bootstrap backend selection and start_session image routing with full suite passing

**Wire bootstrap backend selection and start_session image routing with full suite passing**

## What Happened

Updated bootstrap.py to probe the runtime at construction time and conditionally select OciSandboxRuntime (when preferred_backend == "oci") or DockerSandboxRuntime (default). Updated start_session.py to accept optional runtime_info on StartSessionDependencies, thread it through to _build_sandbox_spec, and route the image: SCC_CLAUDE_IMAGE_REF for OCI backend, SANDBOX_IMAGE for Docker Desktop. Created 9 new tests across two test files for backend selection and image routing. Updated the pre-existing test_bootstrap.py to accept either runtime type since the real probe result is environment-dependent.

## Verification

Ran uv run ruff check (all checks passed), uv run mypy src/scc_cli (246 files, no issues), and uv run pytest --rootdir "$PWD" -q (3353 passed, 23 skipped, 4 xfailed). All three verification commands pass cleanly.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 11000ms |
| 2 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4000ms |
| 3 | `uv run pytest --rootdir "$PWD" -q` | 0 | ✅ pass | 54000ms |

## Deviations

Updated tests/test_bootstrap.py to accept OciSandboxRuntime as valid — the original assertion was hard-coded to DockerSandboxRuntime which fails on environments where Docker Desktop sandbox is unavailable.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/bootstrap.py`
- `src/scc_cli/application/start_session.py`
- `tests/test_bootstrap_backend_selection.py`
- `tests/test_start_session_image_routing.py`
- `tests/test_bootstrap.py`
