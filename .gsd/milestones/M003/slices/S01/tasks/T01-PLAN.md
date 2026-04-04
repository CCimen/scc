---
estimated_steps: 25
estimated_files: 7
skills_used: []
---

# T01: Create RuntimeProbe port, DockerRuntimeProbe adapter, fake, bootstrap wiring, and probe tests

## Description

Build the new typed runtime detection surface: a `RuntimeProbe` protocol, its Docker adapter implementation, a test fake, bootstrap wiring, and comprehensive probe tests. This is the foundation that all subsequent consumer migrations depend on.

## Steps

1. **Extend `RuntimeInfo` in `src/scc_cli/core/contracts.py`** — Add four optional fields with defaults: `version: str | None = None`, `desktop_version: str | None = None`, `daemon_reachable: bool = False`, `sandbox_available: bool = False`. These carry the detection detail that launch gating and future diagnostics need. Keep all existing fields untouched.

2. **Create `src/scc_cli/ports/runtime_probe.py`** — Define a `RuntimeProbe` Protocol with a single method `probe() -> RuntimeInfo`. Follow the existing port pattern (see `platform_probe.py` or `sandbox_runtime.py`).

3. **Create `src/scc_cli/adapters/docker_runtime_probe.py`** — Implement `DockerRuntimeProbe` that calls the existing helpers in `scc_cli.docker.core` (`_check_docker_installed`, `get_docker_version`, `get_docker_desktop_version`, `check_docker_sandbox`, and `run_command_bool(['docker', 'info'])`) to populate a full `RuntimeInfo`. For `rootless`, return `None` (unknown) — rootless detection is S02 scope. Import from `scc_cli.docker` (the package), not from `scc_cli.docker.core` directly. Handle each detection step defensively: if Docker isn't installed, return a `RuntimeInfo` with `daemon_reachable=False`, `sandbox_available=False`, etc. Do not raise exceptions from `probe()` — it returns the truthful state.

4. **Create `tests/fakes/fake_runtime_probe.py`** — A `FakeRuntimeProbe` that returns a configurable `RuntimeInfo`. Constructor takes an optional `RuntimeInfo`; defaults to a fully-capable Docker Desktop scenario.

5. **Wire into bootstrap** — In `src/scc_cli/bootstrap.py`: import `DockerRuntimeProbe` and the `RuntimeProbe` port type. Add `runtime_probe: RuntimeProbe` field to `DefaultAdapters` (after `audit_event_sink`). Construct `DockerRuntimeProbe()` in `get_default_adapters()`. In `tests/fakes/__init__.py`: import `FakeRuntimeProbe`, add it to `build_fake_adapters()` as `runtime_probe=FakeRuntimeProbe()`.

6. **Write `tests/test_runtime_probe.py`** — Test the `DockerRuntimeProbe` adapter with subprocess mocking (patch `scc_cli.docker.core` helpers). Cover at minimum:
   - Docker Desktop present: `_check_docker_installed()=True`, daemon reachable, Desktop version >= 4.50, sandbox available → `RuntimeInfo` with all capabilities true.
   - Docker Engine only: installed, daemon reachable, no Desktop version, no sandbox → `supports_oci=True`, `sandbox_available=False`, `desktop_version=None`.
   - Docker not installed: `_check_docker_installed()=False` → minimal `RuntimeInfo` with everything false/None.
   - Daemon not running: installed but `docker info` returns false → `daemon_reachable=False`.

## Must-Haves

- [ ] `RuntimeInfo` extended with 4 new optional fields, existing fields untouched.
- [ ] `RuntimeProbe` protocol in ports with `probe() -> RuntimeInfo`.
- [ ] `DockerRuntimeProbe` adapter calls existing `docker/core.py` helpers, never raises from `probe()`.
- [ ] `FakeRuntimeProbe` in test fakes with configurable return.
- [ ] `DefaultAdapters` and `build_fake_adapters()` include `runtime_probe` field.
- [ ] `tests/test_runtime_probe.py` covers 4 scenarios and all pass.

## Verification

- `uv run pytest tests/test_runtime_probe.py -q` — all probe tests pass.
- `uv run pytest tests/test_core_contracts.py -q` — existing contract tests still pass (RuntimeInfo backward compatible).
- `uv run ruff check src/scc_cli/ports/runtime_probe.py src/scc_cli/adapters/docker_runtime_probe.py tests/fakes/fake_runtime_probe.py tests/test_runtime_probe.py` — clean.
- `uv run mypy src/scc_cli` — no type errors.

## Inputs

- `src/scc_cli/core/contracts.py`
- `src/scc_cli/ports/sandbox_runtime.py`
- `src/scc_cli/ports/platform_probe.py`
- `src/scc_cli/docker/core.py`
- `src/scc_cli/bootstrap.py`
- `tests/fakes/__init__.py`
- `tests/fakes/fake_sandbox_runtime.py`

## Expected Output

- `src/scc_cli/core/contracts.py`
- `src/scc_cli/ports/runtime_probe.py`
- `src/scc_cli/adapters/docker_runtime_probe.py`
- `tests/fakes/fake_runtime_probe.py`
- `tests/fakes/__init__.py`
- `src/scc_cli/bootstrap.py`
- `tests/test_runtime_probe.py`

## Verification

uv run pytest tests/test_runtime_probe.py tests/test_core_contracts.py -q && uv run ruff check && uv run mypy src/scc_cli
