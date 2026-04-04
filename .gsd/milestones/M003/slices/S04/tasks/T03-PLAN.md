---
estimated_steps: 18
estimated_files: 7
skills_used: []
---

# T03: Add runtime backend doctor check and egress policy support bundle section

Add operator-facing diagnostics: a doctor check for runtime backend type and a support bundle section for effective egress policy.

Steps:
1. Add `check_runtime_backend()` to `src/scc_cli/doctor/checks/environment.py`:
   - Import `DockerRuntimeProbe` from the adapter layer via bootstrap re-export (or use a lightweight probe).
   - Probe the runtime and report `preferred_backend` (docker-sandbox / oci / unavailable) plus `runtime_id` and version.
   - Return `CheckResult` with name `"Runtime Backend"`, pass=True if daemon is reachable, message showing backend type.
   - Handle probe failures gracefully (return warning, not error).
2. Wire `check_runtime_backend()` into the check infrastructure:
   - Add to `run_all_checks()` in `src/scc_cli/doctor/checks/__init__.py` and to `__all__`.
   - Add to `run_doctor()` in `src/scc_cli/doctor/core.py`.
   - Add to `src/scc_cli/doctor/__init__.py` exports.
3. Add `effective_egress` section to `build_support_bundle_manifest()` in `src/scc_cli/application/support_bundle.py`:
   - Include `runtime_backend` (from probe), `network_policy` (from user config if available), and `resolved_destination_sets` (list of set names the active provider requires).
   - Wrap in try/except so probe failures don't crash bundle generation.
4. Write tests:
   - Add tests to `tests/test_doctor_checks.py` for `check_runtime_backend()` — mock the probe to test docker-sandbox, oci, and unavailable cases.
   - Add test to `tests/test_support_bundle.py` for the new `effective_egress` section.
5. Run full suite: `uv run ruff check && uv run mypy src/scc_cli && uv run pytest --rootdir "$PWD" -q`.

## Inputs

- ``src/scc_cli/doctor/checks/environment.py` — existing environment checks to extend`
- ``src/scc_cli/doctor/core.py` — run_doctor() to wire new check`
- ``src/scc_cli/doctor/checks/__init__.py` — run_all_checks() to wire new check`
- ``src/scc_cli/application/support_bundle.py` — build_support_bundle_manifest() to extend`
- ``src/scc_cli/core/destination_registry.py` — PROVIDER_DESTINATION_SETS for support bundle display (from T01)`

## Expected Output

- ``src/scc_cli/doctor/checks/environment.py` — check_runtime_backend() function`
- ``src/scc_cli/doctor/checks/__init__.py` — check_runtime_backend wired into run_all_checks and __all__`
- ``src/scc_cli/doctor/__init__.py` — check_runtime_backend exported`
- ``src/scc_cli/doctor/core.py` — check_runtime_backend called in run_doctor()`
- ``src/scc_cli/application/support_bundle.py` — effective_egress section in manifest`
- ``tests/test_doctor_checks.py` — 3+ new tests for check_runtime_backend`
- ``tests/test_support_bundle.py` — 1+ new test for effective_egress section`

## Verification

uv run ruff check && uv run mypy src/scc_cli && uv run pytest --rootdir "$PWD" tests/test_doctor_checks.py tests/test_support_bundle.py -q && uv run pytest --rootdir "$PWD" -q
