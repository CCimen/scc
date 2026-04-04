---
estimated_steps: 47
estimated_files: 2
skills_used: []
---

# T03: Implement OciSandboxRuntime adapter with subprocess-mocked tests

## Description

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

## Inputs

- `src/scc_cli/ports/sandbox_runtime.py`
- `src/scc_cli/ports/models.py`
- `src/scc_cli/ports/runtime_probe.py`
- `src/scc_cli/core/contracts.py`
- `src/scc_cli/core/constants.py`
- `src/scc_cli/core/errors.py`
- `src/scc_cli/adapters/docker_sandbox_runtime.py`

## Expected Output

- `src/scc_cli/adapters/oci_sandbox_runtime.py`
- `tests/test_oci_sandbox_runtime.py`

## Verification

uv run pytest tests/test_oci_sandbox_runtime.py -q && uv run mypy src/scc_cli/adapters/oci_sandbox_runtime.py
