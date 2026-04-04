# S02: SCC-owned image contracts and plain OCI backend

**Goal:** SCC can launch a sandboxed agent session using standard OCI commands (`docker create`/`docker start`/`docker exec`) when Docker Desktop's sandbox feature is unavailable, selecting the correct backend and image automatically based on runtime probe results.
**Demo:** After this: TBD

## Tasks
- [x] **T01: Add preferred_backend field to RuntimeInfo and rootless detection to DockerRuntimeProbe with five test scenarios** — ## Description

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
  - Estimate: 45m
  - Files: src/scc_cli/core/contracts.py, src/scc_cli/adapters/docker_runtime_probe.py, tests/test_runtime_probe.py, tests/fakes/fake_runtime_probe.py, tests/test_core_contracts.py
  - Verify: uv run pytest tests/test_runtime_probe.py tests/test_core_contracts.py -q && uv run mypy src/scc_cli/core/contracts.py src/scc_cli/adapters/docker_runtime_probe.py
- [x] **T02: Added frozen ImageRef dataclass with full_ref()/image_ref() roundtrip, SCC image constants, and Dockerfiles for scc-base and scc-agent-claude** — ## Description

Create the typed image contract layer and Dockerfiles that define what SCC provides in plain OCI mode. The OCI adapter (T03) and start_session image routing (T04) both consume these constants.

## Steps

1. Create `src/scc_cli/core/image_contracts.py` with:
   a. A frozen `ImageRef` dataclass with fields: `registry: str = ""`, `repository: str`, `tag: str = "latest"`, `digest: str | None = None`.
   b. A `full_ref()` method on `ImageRef` that returns the canonical `registry/repository:tag@digest` string (omitting empty components).
   c. An `image_ref(ref_string: str) -> ImageRef` parse helper that splits a Docker image reference string into the ImageRef fields. Handle common formats: `repo:tag`, `registry/repo:tag`, `registry/repo@sha256:...`, bare `repo` (implies `latest`).
   d. Constants: `SCC_BASE_IMAGE = ImageRef(repository="scc-base", tag="latest")` and `SCC_CLAUDE_IMAGE = ImageRef(repository="scc-agent-claude", tag="latest")`.
   e. A string constant `SCC_CLAUDE_IMAGE_REF = "scc-agent-claude:latest"` for use in SandboxSpec.image (which takes a plain string).
2. Create `images/scc-base/Dockerfile`:
   - `FROM ubuntu:22.04`
   - Install: git, curl, ca-certificates, jq
   - Create agent user: `useradd -m -u 1000 -s /bin/bash agent`
   - Create `/home/agent/.claude/` directory owned by agent
   - Set `USER agent` and `WORKDIR /home/agent`
3. Create `images/scc-agent-claude/Dockerfile`:
   - `FROM scc-base:latest`
   - Install Node.js 20 LTS (via NodeSource or nvm) as root, then switch to agent user
   - Install Claude CLI globally: `npm install -g @anthropic-ai/claude-code`
   - Verify: `claude --version` in a `RUN` step
   - Set `ENTRYPOINT ["/bin/bash"]` (the OCI adapter will exec claude explicitly)
4. Create `tests/test_image_contracts.py`:
   a. Test `ImageRef.full_ref()` for various combinations (with/without registry, digest).
   b. Test `image_ref()` parse helper for standard Docker reference formats.
   c. Test constants: `SCC_BASE_IMAGE.repository == "scc-base"`, `SCC_CLAUDE_IMAGE.repository == "scc-agent-claude"`.
5. Run `uv run pytest tests/test_image_contracts.py -q && uv run mypy src/scc_cli/core/image_contracts.py`.

## Must-Haves

- Frozen `ImageRef` dataclass with `full_ref()` method and `image_ref()` parser
- `SCC_BASE_IMAGE`, `SCC_CLAUDE_IMAGE`, `SCC_CLAUDE_IMAGE_REF` constants
- `images/scc-base/Dockerfile` with agent user (uid 1000), git, curl
- `images/scc-agent-claude/Dockerfile` building on scc-base with Node.js + Claude CLI
- Unit tests for ImageRef parsing and constants
  - Estimate: 40m
  - Files: src/scc_cli/core/image_contracts.py, images/scc-base/Dockerfile, images/scc-agent-claude/Dockerfile, tests/test_image_contracts.py
  - Verify: uv run pytest tests/test_image_contracts.py -q && uv run mypy src/scc_cli/core/image_contracts.py
- [x] **T03: Implemented OciSandboxRuntime adapter using docker create/start/exec with 34 subprocess-mocked tests covering all SandboxRuntime protocol methods** — ## Description

Build the `OciSandboxRuntime` adapter implementing `SandboxRuntime` using standard OCI commands (`docker create`/`docker start`/`docker exec`) instead of `docker sandbox run`. This is the core deliverable of S02 — it makes SCC work on Docker Engine, OrbStack, Colima, and any OCI-compatible runtime.

Critical design differences from `DockerSandboxRuntime`:
- Uses `docker create` + `docker start` + `docker exec` instead of `docker sandbox run`
- Actually consumes `spec.image` (Desktop sandbox ignores it)
- Uses volume mounts at container creation time for credential persistence instead of the sandbox symlink pattern
- No dependency on Docker Desktop's sandbox feature

## Steps

1. Create `src/scc_cli/adapters/oci_sandbox_runtime.py` implementing `SandboxRuntime`:
   a. `__init__(self, probe: RuntimeProbe)` — same pattern as `DockerSandboxRuntime`.
   b. `ensure_available(self)` — call `self._probe.probe()`, check: if `version is None` and not `daemon_reachable` → raise `DockerNotFoundError`. If not `daemon_reachable` → raise `DockerDaemonNotRunningError`. If not `supports_oci` → raise a descriptive error. Do NOT check `sandbox_available` — this adapter doesn't need it.
   c. `run(self, spec: SandboxSpec) -> SandboxHandle`:
      - Build container name: `scc-oci-{hash}` based on workspace path.
      - Build `docker create` command with: `--name`, `-v` for workspace mount (spec.workspace_mount.source:spec.workspace_mount.target), `-v` for credential volume (`SANDBOX_DATA_VOLUME:/home/agent/.claude`), `-w` for workdir, `-e` for each env var, `--label scc.backend=oci`, the image from `spec.image`, and entrypoint `/bin/bash`.
      - If `spec.agent_settings` is not None, plan to inject it after creation.
      - Run `docker create ...` via `subprocess.run`, capture container ID from stdout.
      - Run `docker start <container_id>` to start the container.
      - If agent_settings: write settings JSON to a temp file, `docker cp` it into the container at the settings path.
      - Build `docker exec -it -w <workdir> <container_id> claude --dangerously-skip-permissions` with session flags (`-c` for continue, `--resume` for resume).
      - Call `os.execvp("docker", exec_cmd)` to hand off to the agent.
      - Return `SandboxHandle(sandbox_id=container_id, name=container_name)`.
   d. `resume(self, handle)` — `subprocess.run(["docker", "start", handle.sandbox_id])`.
   e. `stop(self, handle)` — `subprocess.run(["docker", "stop", handle.sandbox_id])`.
   f. `remove(self, handle)` — `subprocess.run(["docker", "rm", "-f", handle.sandbox_id])`.
   g. `list_running(self) -> list[SandboxHandle]` — `docker ps --filter label=scc.backend=oci --format '{{.ID}}\t{{.Names}}'`, parse output.
   h. `status(self, handle)` — `docker inspect --format '{{.State.Status}}' <id>`, map to `SandboxState`.
2. Create `tests/test_oci_sandbox_runtime.py`:
   a. Test `ensure_available` with various `RuntimeInfo` scenarios (mock probe): OCI-capable engine passes, not installed raises `DockerNotFoundError`, daemon not running raises `DockerDaemonNotRunningError`.
   b. Test `run` method: mock `subprocess.run` and `os.execvp`, verify the correct `docker create` command is built with proper `-v`, `-w`, `-e`, `--label` args. Verify `spec.image` is actually consumed.
   c. Test that credential volume mount is present in the create command.
   d. Test `list_running` parsing.
   e. Test `status` mapping from Docker inspect output to SandboxState.
3. Run `uv run pytest tests/test_oci_sandbox_runtime.py -q && uv run mypy src/scc_cli/adapters/oci_sandbox_runtime.py`.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `docker create` subprocess | Raise `SandboxLaunchError` with stderr | 60s timeout, raise `SandboxLaunchError` | Check returncode != 0, raise with stderr |
| `docker start` subprocess | Raise `SandboxLaunchError` | 30s timeout | Check returncode |
| `docker inspect` for status | Return `SandboxState.UNKNOWN` | 10s timeout, return UNKNOWN | Parse defensively, default UNKNOWN |
| `os.execvp` for exec | Raise `SandboxLaunchError` | N/A (replaces process) | N/A |

## Must-Haves

- `OciSandboxRuntime` implements full `SandboxRuntime` protocol
- Uses `docker create` + `docker start` + `docker exec`, NOT `docker sandbox run`
- Actually consumes `spec.image` from `SandboxSpec`
- Mounts credential volume via `-v SANDBOX_DATA_VOLUME:/home/agent/.claude`
- Tests cover ensure_available scenarios, run command construction, and status parsing
- No dependency on Docker Desktop sandbox feature
  - Estimate: 1h30m
  - Files: src/scc_cli/adapters/oci_sandbox_runtime.py, tests/test_oci_sandbox_runtime.py
  - Verify: uv run pytest tests/test_oci_sandbox_runtime.py -q && uv run mypy src/scc_cli/adapters/oci_sandbox_runtime.py
- [ ] **T04: Wire bootstrap backend selection and start_session image routing, run full suite** — ## Description

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
  - Estimate: 1h
  - Files: src/scc_cli/bootstrap.py, src/scc_cli/application/start_session.py, tests/fakes/__init__.py, tests/test_bootstrap_backend_selection.py, tests/test_start_session_image_routing.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest --rootdir "$PWD" -q
