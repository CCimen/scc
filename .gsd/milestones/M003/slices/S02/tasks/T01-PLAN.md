---
estimated_steps: 25
estimated_files: 5
skills_used: []
---

# T01: Extend RuntimeInfo with rootless detection and preferred_backend, update probe and tests

## Description

RuntimeInfo needs two additions before the OCI adapter or bootstrap wiring can work: (1) populate the existing `rootless: bool | None = None` field with actual detection results, and (2) add a new `preferred_backend: str | None` field that downstream code uses to select `DockerSandboxRuntime` vs `OciSandboxRuntime`.

The `rootless` field already exists on `RuntimeInfo` but is always `None`. `DockerRuntimeProbe.probe()` must detect rootless mode by inspecting `docker info --format '{{.SecurityOptions}}'` output for the string `rootless`. Defensive handling: if the command fails or the format is unexpected, leave `rootless = None` (unknown).

`preferred_backend` is a new optional string field on `RuntimeInfo`. Logic in `DockerRuntimeProbe.probe()`: if `sandbox_available` is True → `"docker-sandbox"`. Else if `daemon_reachable` and `supports_oci` → `"oci"`. Else → `None`.

## Steps

1. Add `preferred_backend: str | None = None` field to `RuntimeInfo` in `src/scc_cli/core/contracts.py` (after `sandbox_available`).
2. In `DockerRuntimeProbe.probe()` in `src/scc_cli/adapters/docker_runtime_probe.py`:
   a. After the `daemon_reachable` check, run `docker info --format '{{.SecurityOptions}}'` via `run_command` with timeout=5. Parse output: if the string `rootless` appears in the result → `rootless=True`, else `rootless=False`. If the command fails → `rootless=None`.
   b. Before each `return RuntimeInfo(...)`, compute `preferred_backend`: sandbox_available → `"docker-sandbox"`, daemon_reachable and supports_oci → `"oci"`, otherwise `None`. Pass it.
   c. Import `run_command` from the same re-export path already used (it's already available via `scc_cli.docker`).
3. Update `tests/fakes/fake_runtime_probe.py`: add `preferred_backend="docker-sandbox"` to `_DEFAULT_RUNTIME_INFO`.
4. Update `tests/test_runtime_probe.py`:
   a. In `TestDockerRuntimeProbeDesktopPresent`: patch `run_command` in the adapter module to return a CompletedProcess with stdout containing `name=rootless`. Assert `info.rootless is True` and `info.preferred_backend == "docker-sandbox"`.
   b. In `TestDockerRuntimeProbeEngineOnly`: patch `run_command` to return stdout without `rootless`. Assert `info.rootless is False` and `info.preferred_backend == "oci"`.
   c. In `TestDockerRuntimeProbeNotInstalled`: assert `info.preferred_backend is None`.
   d. In `TestDockerRuntimeProbeDaemonNotRunning`: assert `info.preferred_backend is None`.
   e. Add a new test class `TestDockerRuntimeProbeRootlessDetectionFailure`: patch `run_command` to raise an exception. Assert `info.rootless is None` (graceful fallback).
5. Update `tests/test_core_contracts.py` if it constructs RuntimeInfo — add `preferred_backend` to match the new field.
6. Run `uv run pytest tests/test_runtime_probe.py tests/test_core_contracts.py tests/fakes/ -q` and `uv run mypy src/scc_cli/core/contracts.py src/scc_cli/adapters/docker_runtime_probe.py`.

## Must-Haves

- `preferred_backend` field on RuntimeInfo with `None` default
- Rootless detection via `docker info` SecurityOptions parsing, graceful fallback to `None`
- `preferred_backend` logic: sandbox → `"docker-sandbox"`, daemon+OCI → `"oci"`, else `None`
- All four existing probe test scenarios updated with assertions for new fields
- New test for rootless detection failure (graceful `None` fallback)

## Inputs

- `src/scc_cli/core/contracts.py`
- `src/scc_cli/adapters/docker_runtime_probe.py`
- `tests/test_runtime_probe.py`
- `tests/fakes/fake_runtime_probe.py`
- `tests/test_core_contracts.py`

## Expected Output

- `src/scc_cli/core/contracts.py`
- `src/scc_cli/adapters/docker_runtime_probe.py`
- `tests/test_runtime_probe.py`
- `tests/fakes/fake_runtime_probe.py`
- `tests/test_core_contracts.py`

## Verification

uv run pytest tests/test_runtime_probe.py tests/test_core_contracts.py -q && uv run mypy src/scc_cli/core/contracts.py src/scc_cli/adapters/docker_runtime_probe.py
