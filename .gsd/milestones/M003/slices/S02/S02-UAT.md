# S02: SCC-owned image contracts and plain OCI backend — UAT

**Milestone:** M003
**Written:** 2026-04-04T09:25:06.612Z

## UAT: S02 — SCC-owned image contracts and plain OCI backend

### Preconditions
- Python 3.10+ with uv installed
- Repository checked out at scc-sync-1.7.3 with all S02 changes applied
- Docker Engine or Docker Desktop available for integration scenarios

---

### TC-01: RuntimeInfo preferred_backend field contract
**Steps:**
1. Run `uv run pytest tests/test_runtime_probe.py -q`
2. Inspect test output for all 5 test classes passing

**Expected:**
- TestDockerRuntimeProbeDesktopPresent: `preferred_backend == "docker-sandbox"`, `rootless is True` (mocked SecurityOptions contains rootless)
- TestDockerRuntimeProbeEngineOnly: `preferred_backend == "oci"`, `rootless is False`
- TestDockerRuntimeProbeNotInstalled: `preferred_backend is None`
- TestDockerRuntimeProbeDaemonNotRunning: `preferred_backend is None`
- TestDockerRuntimeProbeRootlessDetectionFailure: `rootless is None` (graceful fallback)

---

### TC-02: ImageRef parsing roundtrip
**Steps:**
1. Run `uv run pytest tests/test_image_contracts.py -q`
2. Verify all 23 tests pass

**Expected:**
- `image_ref("ubuntu:22.04")` → `ImageRef(registry="", repository="ubuntu", tag="22.04")`
- `image_ref("ghcr.io/org/repo:v1")` → `ImageRef(registry="ghcr.io", repository="org/repo", tag="v1")`
- `SCC_BASE_IMAGE.repository == "scc-base"`, `SCC_CLAUDE_IMAGE.repository == "scc-agent-claude"`
- `SCC_CLAUDE_IMAGE_REF == "scc-agent-claude:latest"`
- `ImageRef.full_ref()` roundtrips correctly for all format variants

---

### TC-03: OciSandboxRuntime ensure_available validation
**Steps:**
1. Run `uv run pytest tests/test_oci_sandbox_runtime.py -k "ensure_available" -q`

**Expected:**
- OCI-capable engine (daemon_reachable=True, supports_oci=True, sandbox_available=False) → passes without error
- Docker not installed (version=None, daemon_reachable=False) → raises DockerNotFoundError
- Daemon not running (daemon_reachable=False) → raises DockerDaemonNotRunningError

---

### TC-04: OciSandboxRuntime run command construction
**Steps:**
1. Run `uv run pytest tests/test_oci_sandbox_runtime.py -k "run" -q`

**Expected:**
- `docker create` command includes: `-v` for workspace mount, `-v` for credential volume (`/home/agent/.claude`), `-w` for workdir, `-e` for env vars, `--label scc.backend=oci`, the specified image from spec.image
- `docker start` is called with container ID from create
- `os.execvp` is called with `docker exec -it` command including `-w`, container ID, and agent command
- Container name follows `scc-oci-{hash}` pattern

---

### TC-05: OciSandboxRuntime lifecycle and status
**Steps:**
1. Run `uv run pytest tests/test_oci_sandbox_runtime.py -k "status or list_running or stop or remove or resume" -q`

**Expected:**
- `status()` maps Docker inspect output: "running" → RUNNING, "exited" → STOPPED, "created" → STOPPED, "paused" → RUNNING, unknown → UNKNOWN
- `status()` returns UNKNOWN on subprocess failure (does not raise)
- `list_running()` parses `docker ps` output into SandboxHandle list
- `stop()`, `remove()`, `resume()` call correct docker commands

---

### TC-06: Bootstrap backend selection
**Steps:**
1. Run `uv run pytest tests/test_bootstrap_backend_selection.py -q`

**Expected:**
- When probe returns `preferred_backend="oci"` → `get_default_adapters().sandbox_runtime` is `OciSandboxRuntime`
- When probe returns `preferred_backend="docker-sandbox"` → `get_default_adapters().sandbox_runtime` is `DockerSandboxRuntime`
- When probe returns `preferred_backend=None` → defaults to `DockerSandboxRuntime`

---

### TC-07: start_session image routing
**Steps:**
1. Run `uv run pytest tests/test_start_session_image_routing.py -q`

**Expected:**
- With `runtime_info.preferred_backend == "oci"` → `_build_sandbox_spec()` uses `SCC_CLAUDE_IMAGE_REF` ("scc-agent-claude:latest")
- With `runtime_info.preferred_backend == "docker-sandbox"` → uses `SANDBOX_IMAGE` (Desktop image)
- With `runtime_info is None` → uses `SANDBOX_IMAGE` (safe default)

---

### TC-08: Dockerfile structure validation
**Steps:**
1. Inspect `images/scc-base/Dockerfile`:
   - Verify `FROM ubuntu:22.04`
   - Verify `useradd -m -u 1000 -s /bin/bash agent`
   - Verify git, curl, ca-certificates, jq installed
   - Verify `USER agent` and `WORKDIR /home/agent`
2. Inspect `images/scc-agent-claude/Dockerfile`:
   - Verify `FROM scc-base:latest`
   - Verify Node.js 20 LTS installation
   - Verify `npm install -g @anthropic-ai/claude-code`
   - Verify `claude --version` validation step

**Expected:** Both Dockerfiles are syntactically valid and follow the specified layering.

---

### TC-09: Import boundary compliance
**Steps:**
1. Run `uv run pytest tests/test_import_boundaries.py -q`

**Expected:**
- `OciSandboxRuntime` is imported only in `bootstrap.py`, not in `application/` or `commands/`
- `image_contracts` (a core module) is importable from `application/start_session.py` — this is allowed since it's in `core/`, not `adapters/`

---

### TC-10: Full suite regression
**Steps:**
1. Run `uv run ruff check`
2. Run `uv run mypy src/scc_cli`
3. Run `uv run pytest --rootdir "$PWD" -q`

**Expected:**
- ruff: All checks passed
- mypy: Success, no issues found in 246 source files
- pytest: 3353+ passed, 23 skipped, 4 xfailed, 0 failed
