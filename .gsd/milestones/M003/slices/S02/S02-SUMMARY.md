---
id: S02
parent: M003
milestone: M003
provides:
  - OciSandboxRuntime adapter implementing full SandboxRuntime protocol
  - ImageRef dataclass and SCC image constants (SCC_BASE_IMAGE, SCC_CLAUDE_IMAGE, SCC_CLAUDE_IMAGE_REF)
  - RuntimeInfo.preferred_backend field for downstream backend selection
  - RuntimeInfo.rootless detection via docker info SecurityOptions
  - Bootstrap auto-selection of OCI vs Docker Desktop runtime
  - start_session image routing based on preferred_backend
  - Dockerfile definitions for scc-base and scc-agent-claude images
requires:
  - slice: S01
    provides: RuntimeProbe protocol, DockerRuntimeProbe adapter, RuntimeInfo with version/daemon_reachable/sandbox_available/supports_oci fields, bootstrap probe sharing pattern
affects:
  - S03
  - S04
key_files:
  - src/scc_cli/core/contracts.py
  - src/scc_cli/core/image_contracts.py
  - src/scc_cli/adapters/docker_runtime_probe.py
  - src/scc_cli/adapters/oci_sandbox_runtime.py
  - src/scc_cli/bootstrap.py
  - src/scc_cli/application/start_session.py
  - images/scc-base/Dockerfile
  - images/scc-agent-claude/Dockerfile
  - tests/test_runtime_probe.py
  - tests/test_image_contracts.py
  - tests/test_oci_sandbox_runtime.py
  - tests/test_bootstrap_backend_selection.py
  - tests/test_start_session_image_routing.py
key_decisions:
  - D013: OCI sandbox backend introduced as parallel adapter, not replacement. Bootstrap selects based on RuntimeInfo.preferred_backend.
  - preferred_backend uses literal strings ('docker-sandbox', 'oci') rather than enum, matching lightweight RuntimeInfo design
  - OCI adapter uses sleep infinity entrypoint + os.execvp for docker exec handoff
  - Credential persistence via explicit -v volume mount in OCI path (vs Desktop's symlink pattern)
  - Container naming is deterministic via scc-oci-{sha256(workspace)[:12]}
  - runtime_info threaded as optional field on StartSessionDependencies with None default to avoid breaking construction sites
  - Image routing: SCC_CLAUDE_IMAGE_REF for OCI, SANDBOX_IMAGE for Docker Desktop
patterns_established:
  - OciSandboxRuntime: full SandboxRuntime implementation using create/start/exec instead of sandbox run — reusable pattern for any OCI-compatible runtime
  - Frozen ImageRef dataclass with full_ref()/image_ref() roundtrip — canonical way to reference SCC-managed images
  - _run_docker helper pattern: centralized subprocess error handling with per-command timeouts and SandboxLaunchError wrapping
  - Bootstrap probe-at-construction-time pattern: probe once, select adapter, share probe instance
  - scc.backend=oci label convention for filtering OCI-managed containers from Docker Desktop ones
observability_surfaces:
  - scc.backend=oci Docker label on all OCI-created containers enables filtered docker ps queries
  - Container naming convention scc-oci-{hash} provides deterministic workspace-to-container mapping
drill_down_paths:
  - .gsd/milestones/M003/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M003/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M003/slices/S02/tasks/T03-SUMMARY.md
  - .gsd/milestones/M003/slices/S02/tasks/T04-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-04T09:25:06.612Z
blocker_discovered: false
---

# S02: SCC-owned image contracts and plain OCI backend

**SCC can now launch sandboxed agent sessions using standard OCI commands (docker create/start/exec) when Docker Desktop sandbox is unavailable, with typed image contracts, rootless detection, and automatic backend selection wired through bootstrap.**

## What Happened

S02 delivered four tasks that together create a complete OCI-based sandbox backend operating in parallel with the existing Docker Desktop path.

**T01 — RuntimeInfo extensions.** Added `preferred_backend: str | None` to RuntimeInfo and rootless detection via `docker info --format '{{.SecurityOptions}}'` to DockerRuntimeProbe. The preferred_backend field drives downstream backend selection: `"docker-sandbox"` when Desktop sandbox is available, `"oci"` when the daemon is reachable with OCI support but no sandbox, and `None` otherwise. Rootless detection uses graceful `None` fallback on any failure. All four existing probe test scenarios were extended with new field assertions, plus a new test class for rootless detection failure.

**T02 — Image contracts and Dockerfiles.** Created `src/scc_cli/core/image_contracts.py` with a frozen `ImageRef` dataclass, a `full_ref()` method for canonical reference rendering, an `image_ref()` parser for Docker reference strings, and constants `SCC_BASE_IMAGE`, `SCC_CLAUDE_IMAGE`, `SCC_CLAUDE_IMAGE_REF`. Two Dockerfiles define the SCC image stack: `images/scc-base/Dockerfile` (Ubuntu 22.04, git, curl, agent user uid 1000) and `images/scc-agent-claude/Dockerfile` (Node.js 20 LTS, Claude CLI). 23 unit tests cover parsing, roundtrip, and constant correctness.

**T03 — OciSandboxRuntime adapter.** The core deliverable: a full `SandboxRuntime` implementation using `docker create` + `docker start` + `docker exec` instead of `docker sandbox run`. Key design choices: `sleep infinity` entrypoint keeps the container alive for exec; credential persistence via explicit `-v` volume mount (not Desktop's symlink pattern); `scc.backend=oci` label for filtering; deterministic container naming via `scc-oci-{sha256(workspace)[:12]}`; a `_run_docker` helper centralizing subprocess error handling with per-command timeouts; and `os.execvp` for process handoff to the agent. 34 tests across 7 test classes cover ensure_available scenarios, run command construction, failure modes, list_running parsing, status mapping, lifecycle methods, and container naming.

**T04 — Bootstrap wiring and image routing.** Integration closure: `bootstrap.py` now probes the runtime at construction time and selects OciSandboxRuntime when `preferred_backend == "oci"`, DockerSandboxRuntime otherwise. `start_session.py` routes the image: `SCC_CLAUDE_IMAGE_REF` for OCI backend, `SANDBOX_IMAGE` for Desktop. `runtime_info` is threaded as an optional field on `StartSessionDependencies` with a `None` default to avoid breaking any construction sites. 9 new tests verify backend selection and image routing. Pre-existing `test_bootstrap.py` was updated to accept either runtime type since probe results are environment-dependent.

## Verification

All three slice-level verification gates pass on the assembled codebase:
- `uv run ruff check` → All checks passed!
- `uv run mypy src/scc_cli` → Success: no issues found in 246 source files
- `uv run pytest --rootdir "$PWD" -q` → 3353 passed, 23 skipped, 4 xfailed in 53.89s

Task-specific verifications (all passed during execution):
- T01: 16 targeted tests + full suite (3287 passed)
- T02: 23 image contract tests + mypy clean
- T03: 34 OCI runtime tests + full suite (3344 passed)
- T04: 9 new integration tests + full suite (3353 passed)

## Requirements Advanced

- R001 — OciSandboxRuntime follows adapter-boundary conventions from D003/D012, uses typed contracts, centralizes error handling in _run_docker helper, and keeps bootstrap as sole composition root. Image contracts are a frozen typed module with full test coverage. No monolith growth in touched files.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

Minor deviations from the plan, all documented in task summaries:
- T03: Used `sleep infinity` as container entrypoint instead of `/bin/bash` — necessary to keep the container alive for docker exec.
- T04: Updated existing test_bootstrap.py to accept either DockerSandboxRuntime or OciSandboxRuntime since probe results are environment-dependent. The original assertion was hard-coded to DockerSandboxRuntime.

## Known Limitations

- Dockerfiles (`images/scc-base/`, `images/scc-agent-claude/`) are defined but not built or pushed to any registry. The OCI path currently assumes images are available locally. A future slice or milestone will need to address image distribution (registry push, local build on first run, or bundled build step).
- The `preferred_backend` field uses literal strings ("docker-sandbox", "oci") rather than an enum. This was a deliberate plan-level decision to keep RuntimeInfo lightweight, but should be revisited if more backends are added.

## Follow-ups

- S03 depends on S02's OCI backend for enforced web-egress topology — the egress enforcement layer needs to work with both Docker Desktop and plain OCI containers.
- S04 depends on S02's image contracts and backend selection for provider destination validation.
- Image build/distribution strategy needs to be defined before real OCI launches work end-to-end (likely an M003/S04 or S05 concern).

## Files Created/Modified

- `src/scc_cli/core/contracts.py` — Added preferred_backend: str | None = None field to RuntimeInfo
- `src/scc_cli/adapters/docker_runtime_probe.py` — Added rootless detection via docker info SecurityOptions and preferred_backend computation
- `src/scc_cli/core/image_contracts.py` — New file: frozen ImageRef dataclass, full_ref/image_ref helpers, SCC image constants
- `src/scc_cli/adapters/oci_sandbox_runtime.py` — New file: OciSandboxRuntime implementing full SandboxRuntime protocol via docker create/start/exec
- `src/scc_cli/bootstrap.py` — Probes runtime at construction time, selects OciSandboxRuntime or DockerSandboxRuntime based on preferred_backend
- `src/scc_cli/application/start_session.py` — Added runtime_info to StartSessionDependencies, routes image selection based on preferred_backend
- `images/scc-base/Dockerfile` — New file: Ubuntu 22.04 base image with git, curl, agent user
- `images/scc-agent-claude/Dockerfile` — New file: Node.js 20 LTS + Claude CLI on top of scc-base
- `tests/test_runtime_probe.py` — Extended all 4 existing test classes with preferred_backend/rootless assertions, added rootless failure test
- `tests/fakes/fake_runtime_probe.py` — Added preferred_backend to default RuntimeInfo
- `tests/test_image_contracts.py` — New file: 23 tests for ImageRef parsing, roundtrip, and constants
- `tests/test_oci_sandbox_runtime.py` — New file: 34 tests covering all OciSandboxRuntime protocol methods
- `tests/test_bootstrap_backend_selection.py` — New file: 4 tests for bootstrap backend selection logic
- `tests/test_start_session_image_routing.py` — New file: 5 tests for image routing based on preferred_backend
- `tests/test_bootstrap.py` — Updated to accept either runtime type since probe result is environment-dependent
