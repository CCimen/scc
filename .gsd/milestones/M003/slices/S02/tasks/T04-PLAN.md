---
estimated_steps: 36
estimated_files: 5
skills_used: []
---

# T04: Wire bootstrap backend selection and start_session image routing, run full suite

## Description

Integration closure: wire bootstrap to conditionally construct `OciSandboxRuntime` when the probe says `preferred_backend == "oci"`, and update `_build_sandbox_spec()` in `start_session.py` to select the right image based on the active backend. This task makes the whole slice work end-to-end.

Key constraint from KNOWLEDGE.md: `bootstrap.py` is the composition root — adapters must be imported there and re-exported. Application and command layers must not import directly from `scc_cli.adapters.*`.

## Steps

1. Update `src/scc_cli/bootstrap.py`:
   a. Import `OciSandboxRuntime` from `scc_cli.adapters.oci_sandbox_runtime`.
   b. In `get_default_adapters()`, after `probe = DockerRuntimeProbe()`, call `info = probe.probe()` to get RuntimeInfo.
   c. Select sandbox runtime: if `info.preferred_backend == "oci"` → `OciSandboxRuntime(probe=probe)`, else → `DockerSandboxRuntime(probe=probe)` (preserves current default).
   d. Pass the selected runtime to `sandbox_runtime=` in the `DefaultAdapters` constructor.
2. Update `src/scc_cli/application/start_session.py`:
   a. Import `SCC_CLAUDE_IMAGE_REF` from `scc_cli.core.image_contracts`.
   b. Add `runtime_info: RuntimeInfo | None = None` field to `StartSessionDependencies` with `None` default.
   c. In `_build_sandbox_spec()`, accept the runtime_info (thread it from the dependencies or pass it through the request). If `runtime_info` is not None and `runtime_info.preferred_backend == "oci"` → use `SCC_CLAUDE_IMAGE_REF` as the image. Otherwise → use `SANDBOX_IMAGE` (current default).
   d. Alternative simpler approach: just pass runtime_info to `_build_sandbox_spec` from `prepare_start_session`, where dependencies carry it. The caller (`prepare_start_session`) can read it from `dependencies.runtime_info` if available.
3. Update `tests/fakes/__init__.py`:
   a. Ensure `build_fake_adapters()` still works — the `FakeRuntimeProbe` default has `sandbox_available=True` and should now also have `preferred_backend="docker-sandbox"`, so `DockerSandboxRuntime` is the default in test wiring.
4. Create `tests/test_bootstrap_backend_selection.py`:
   a. Test that when probe returns `preferred_backend="oci"`, `get_default_adapters()` produces an `OciSandboxRuntime`.
   b. Test that when probe returns `preferred_backend="docker-sandbox"`, `get_default_adapters()` produces a `DockerSandboxRuntime`.
   c. Mock `DockerRuntimeProbe.probe()` to return controlled RuntimeInfo for each case.
   d. Clear the `lru_cache` before each test: `get_default_adapters.cache_clear()`.
5. Create or extend `tests/test_start_session_image_routing.py`:
   a. Test that `_build_sandbox_spec()` returns `SCC_CLAUDE_IMAGE_REF` when RuntimeInfo has `preferred_backend="oci"`.
   b. Test that `_build_sandbox_spec()` returns `SANDBOX_IMAGE` when RuntimeInfo has `preferred_backend="docker-sandbox"` or is None.
6. Run full verification:
   - `uv run ruff check`
   - `uv run mypy src/scc_cli`
   - `uv run pytest --rootdir "$PWD" -q` (full suite)

## Must-Haves

- Bootstrap selects `OciSandboxRuntime` when `preferred_backend == "oci"`
- Bootstrap defaults to `DockerSandboxRuntime` when sandbox is available or backend is unknown
- `_build_sandbox_spec()` routes to SCC image for OCI backend
- `_build_sandbox_spec()` preserves `SANDBOX_IMAGE` for Docker Desktop path
- Import boundary: `OciSandboxRuntime` imported only in `bootstrap.py`, not in application layer
- Tests verify both backend selection and image routing
- Full suite passes: ruff, mypy, pytest

## Inputs

- `src/scc_cli/bootstrap.py`
- `src/scc_cli/application/start_session.py`
- `src/scc_cli/adapters/oci_sandbox_runtime.py`
- `src/scc_cli/core/image_contracts.py`
- `src/scc_cli/core/contracts.py`
- `tests/fakes/__init__.py`
- `tests/fakes/fake_runtime_probe.py`

## Expected Output

- `src/scc_cli/bootstrap.py`
- `src/scc_cli/application/start_session.py`
- `tests/test_bootstrap_backend_selection.py`
- `tests/test_start_session_image_routing.py`
- `tests/fakes/__init__.py`

## Verification

uv run ruff check && uv run mypy src/scc_cli && uv run pytest --rootdir "$PWD" -q
