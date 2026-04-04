# S01: Capability-based runtime model and detection cleanup — UAT

**Milestone:** M003
**Written:** 2026-04-04T08:46:01.166Z

## UAT: S01 — Capability-based runtime model and detection cleanup

### Preconditions
- Working directory is the scc-sync-1.7.3 repo root.
- Python 3.10+ with `uv` available.
- All dependencies installed via `uv sync`.

---

### Test 1: RuntimeProbe protocol exists and is importable
**Steps:**
1. Run `uv run python -c "from scc_cli.ports.runtime_probe import RuntimeProbe; print('OK')"`
**Expected:** Prints `OK` with exit code 0.

### Test 2: DockerRuntimeProbe adapter is importable and instantiable
**Steps:**
1. Run `uv run python -c "from scc_cli.adapters.docker_runtime_probe import DockerRuntimeProbe; p = DockerRuntimeProbe(); print(type(p).__name__)"`
**Expected:** Prints `DockerRuntimeProbe` with exit code 0.

### Test 3: RuntimeInfo has new detection fields with backward-compatible defaults
**Steps:**
1. Run `uv run python -c "from scc_cli.core.contracts import RuntimeInfo; ri = RuntimeInfo(); print(ri.version, ri.desktop_version, ri.daemon_reachable, ri.sandbox_available)"`
**Expected:** Prints `None None False False` — all new fields have safe defaults.

### Test 4: Four-scenario probe tests pass
**Steps:**
1. Run `uv run pytest tests/test_runtime_probe.py -v`
**Expected:** Four tests pass: Docker Desktop present, Engine only, not installed, daemon not running. Each test verifies correct RuntimeInfo field values for the scenario.

### Test 5: DockerSandboxRuntime.ensure_available() uses probe (not docker.check_docker_available)
**Steps:**
1. Run `uv run python -c "import inspect; from scc_cli.adapters.docker_sandbox_runtime import DockerSandboxRuntime; src = inspect.getsource(DockerSandboxRuntime.ensure_available); assert 'probe' in src; assert 'check_docker_available' not in src; print('OK')"`
**Expected:** Prints `OK` — ensure_available references probe, not the old direct call.

### Test 6: Bootstrap wires shared probe instance
**Steps:**
1. Run `uv run python -c "from scc_cli.bootstrap import get_default_adapters; a = get_default_adapters(); print(a.runtime_probe is not None)"`
**Expected:** Prints `True`.

### Test 7: Dashboard orchestrator no longer imports docker.check_docker_available
**Steps:**
1. Run `grep -n 'check_docker_available' src/scc_cli/ui/dashboard/orchestrator.py`
**Expected:** No output (exit code 1) — the orchestrator no longer references this function.

### Test 8: Guardrail test catches violations
**Steps:**
1. Run `uv run pytest tests/test_runtime_detection_hotspots.py -v`
**Expected:** 1 test passes. The guardrail scans all .py files under src/scc_cli/ and asserts no code-level references to check_docker_available exist outside the three allowed files.

### Test 9: Existing contract tests remain green
**Steps:**
1. Run `uv run pytest tests/test_core_contracts.py tests/contracts/test_sandbox_runtime_contract.py -v`
**Expected:** All existing tests pass — RuntimeInfo extensions are backward compatible, sandbox runtime contract behavior is preserved.

### Test 10: Full suite green
**Steps:**
1. Run `uv run pytest --rootdir "$PWD" -q`
**Expected:** 3286+ passed, 0 failed. The slice did not break any existing behavior.

### Edge Cases

#### E1: FakeRuntimeProbe defaults to fully-capable scenario
**Steps:**
1. Run `uv run python -c "from tests.fakes.fake_runtime_probe import FakeRuntimeProbe; f = FakeRuntimeProbe(); ri = f.probe(); print(ri.daemon_reachable, ri.sandbox_available)"`
**Expected:** Prints `True True` — the fake defaults to a Docker Desktop scenario.

#### E2: FakeRuntimeProbe accepts custom RuntimeInfo
**Steps:**
1. Run `uv run python -c "from tests.fakes.fake_runtime_probe import FakeRuntimeProbe; from scc_cli.core.contracts import RuntimeInfo; ri = RuntimeInfo(daemon_reachable=False); f = FakeRuntimeProbe(ri); print(f.probe().daemon_reachable)"`
**Expected:** Prints `False` — the fake returns the custom RuntimeInfo.
