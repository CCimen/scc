# S02 — Research: SCC-owned image contracts and plain OCI backend

**Date:** 2026-04-04

## Summary

S02 introduces a plain OCI runtime backend that replaces the Docker Desktop-only `docker sandbox run` path with standard `docker run`/`docker create`/`docker exec` commands. Today the entire launch flow is hardwired to Docker Desktop's proprietary sandbox CLI — `build_command()` generates `docker sandbox run ... claude`, credential management uses the detached sandbox pattern, and image references point to Docker's `docker/sandbox-templates:claude-code`. None of this works on Docker Engine, OrbStack, or Colima.

The work has three parts: (1) define SCC-owned image contracts — typed `ImageRef` model plus Dockerfiles for `scc-base` and `scc-agent-claude`; (2) build an `OciSandboxRuntime` adapter that implements the existing `SandboxRuntime` protocol using standard OCI commands; (3) extend `RuntimeProbe`/`RuntimeInfo` with rootless detection and a `preferred_backend` field so bootstrap can wire the right runtime. The egress proxy image (`scc-egress-proxy`) is S03 scope and not part of this slice.

## Recommendation

**Build contracts and adapter in three phases**: First, extend RuntimeInfo and RuntimeProbe (rootless, OCI backend detection) since downstream tasks depend on these fields. Second, define the image contracts — a typed `ImageRef` dataclass and minimal Dockerfiles for `scc-base` (agent user, git, common tools) and `scc-agent-claude` (Claude CLI on top of base). Third, implement `OciSandboxRuntime` as a new adapter parallel to `DockerSandboxRuntime`, wired through bootstrap based on probe results. Keep the Docker Desktop sandbox path untouched — plain OCI is an additional backend, not a replacement. This slice does not need to publish images to a registry; local `docker build` is sufficient for verification.

## Implementation Landscape

### Key Files

- `src/scc_cli/core/contracts.py` — `RuntimeInfo` needs two additions: (a) populate `rootless` (currently always `None`) and (b) a new `preferred_backend: str | None` field indicating `"docker-sandbox"` or `"oci"` so downstream code can select the runtime adapter without re-probing.
- `src/scc_cli/ports/runtime_probe.py` — `RuntimeProbe` protocol stays the same (`probe() -> RuntimeInfo`); the new fields flow through `RuntimeInfo`.
- `src/scc_cli/adapters/docker_runtime_probe.py` — `DockerRuntimeProbe.probe()` must detect rootless mode (check `docker info --format '{{.SecurityOptions}}'` for `rootless` or inspect `/proc/self/uid_map`) and decide `preferred_backend` based on `sandbox_available`: if sandbox is available → `"docker-sandbox"`, otherwise if daemon is reachable and OCI is supported → `"oci"`, else `None`.
- `src/scc_cli/ports/models.py` — `SandboxSpec.image` already exists and is already a `str`. The `OciSandboxRuntime` should consume it directly. Consider adding a typed `ImageRef` frozen dataclass alongside for structured image references (registry, repo, tag, digest).
- `src/scc_cli/adapters/docker_sandbox_runtime.py` — Remains the Docker Desktop backend. No changes needed except possibly renaming to clarify it handles the sandbox-specific path. Keep it untouched in S02.
- **New file**: `src/scc_cli/adapters/oci_sandbox_runtime.py` — New `OciSandboxRuntime` implementing `SandboxRuntime`. Uses `docker create`/`docker start`/`docker exec` instead of `docker sandbox run`. Must handle: workspace mounts (`-v`), env vars (`-e`), working directory (`-w`), credential setup (volume mounts instead of sandbox credential symlinks), and agent settings injection.
- **New file**: `src/scc_cli/core/image_contracts.py` — Typed image definitions: `ImageRef` dataclass (registry, repository, tag, digest), constants for SCC image references (`SCC_BASE_IMAGE`, `SCC_CLAUDE_IMAGE`), and an `image_ref()` helper for parsing image strings.
- **New directory**: `images/` at repo root — Dockerfiles for `scc-base/Dockerfile` and `scc-agent-claude/Dockerfile`. These define the contract; local builds verify them.
- `src/scc_cli/bootstrap.py` — Must wire either `DockerSandboxRuntime` or `OciSandboxRuntime` based on `RuntimeInfo.preferred_backend` from the probe. The probe runs once; both the runtime_probe field and sandbox_runtime field derive from it.
- `src/scc_cli/application/start_session.py` — `_build_sandbox_spec()` currently hardcodes `image=SANDBOX_IMAGE`. This needs to select the right image based on the active backend: Docker Desktop sandbox image for `"docker-sandbox"`, SCC-owned image for `"oci"`.
- `src/scc_cli/core/constants.py` — `SANDBOX_IMAGE` stays for Docker Desktop path. Add new SCC image constants or import from `image_contracts.py`.
- `tests/fakes/fake_runtime_probe.py` — Update default RuntimeInfo to include `rootless` and `preferred_backend` fields.
- `tests/fakes/__init__.py` — `build_fake_adapters()` already handles the wiring; may need adjustment if bootstrap selection logic changes.

### Build Order

1. **RuntimeInfo + RuntimeProbe extensions** — Add `rootless` detection and `preferred_backend` to RuntimeInfo/DockerRuntimeProbe. This is the foundation S03 also depends on. Write characterization tests for rootless detection. This unblocks everything else.

2. **Image contracts** — Define `ImageRef` dataclass in `core/image_contracts.py`. Write Dockerfiles for `scc-base` and `scc-agent-claude`. `scc-base` should be a minimal Linux image with: non-root agent user (uid 1000), git, curl, and a `/home/agent/.claude/` directory structure. `scc-agent-claude` builds on base and installs the Claude CLI. The Dockerfiles themselves are the contract — they document exactly what SCC provides.

3. **OciSandboxRuntime adapter** — Implement the new adapter. The critical difference from DockerSandboxRuntime: it uses `docker create` + `docker start` + `docker exec` instead of `docker sandbox run`. Credential handling must use volume mounts (the `SANDBOX_DATA_VOLUME` pattern already exists in `credentials.py`). The adapter must pass `ensure_available()` using RuntimeInfo just like DockerSandboxRuntime does, but check for OCI capability instead of sandbox availability.

4. **Bootstrap wiring and start_session image selection** — Wire the right runtime in bootstrap based on probe. Update `_build_sandbox_spec()` to select the image based on backend.

5. **Tests** — Contract test for OciSandboxRuntime (extend `test_sandbox_runtime_contract.py` pattern). Probe tests for rootless detection. Image reference parsing tests. Guard test to ensure `image` field in SandboxSpec is consumed by OCI backend.

### Verification Approach

- `uv run pytest tests/test_runtime_probe.py -q` — Extended probe tests including rootless and preferred_backend
- `uv run pytest tests/contracts/test_sandbox_runtime_contract.py -q` — Contract test passes for both DockerSandboxRuntime and OciSandboxRuntime
- `uv run ruff check` — All checks pass
- `uv run mypy src/scc_cli` — No type errors
- `uv run pytest --rootdir "$PWD" -q` — Full suite green
- `docker build -t scc-base images/scc-base/` — Dockerfiles build locally (manual verification, not CI)

## Constraints

- **Constitution §3**: "No hard Docker Desktop dependency." — The OCI backend is the direct implementation of this rule. The existing Docker Desktop sandbox path remains as an optimization when available, not a requirement.
- **Constitution §6**: "Provider-specific behavior belongs in adapters." — The OCI backend must not embed Claude-specific or Codex-specific logic. Image selection is driven by `SandboxSpec.image`, which is set by the application layer based on provider.
- **KNOWLEDGE.md**: "Do not make Docker Desktop a required dependency." — This is the primary motivator for S02.
- **KNOWLEDGE.md**: "When adding a new field to a shared dataclass, grep for all construction sites." — `RuntimeInfo` is constructed in `DockerRuntimeProbe`, `FakeRuntimeProbe`, and tests. All must be updated when adding fields with defaults.
- The existing `docker sandbox run` credential pattern (detached → symlink → exec) is Docker Desktop-specific. The OCI backend must use a different credential strategy based on standard volume mounts.
- The `alpine` helper container pattern (used 16 times in `credentials.py` and `launch.py` for volume operations) works with plain Docker too, so it can be reused.

## Common Pitfalls

- **SandboxSpec.image is unused today** — `DockerSandboxRuntime.run()` ignores `spec.image` entirely; the image is implicit in `docker sandbox run ... claude`. The OCI backend must actually use it, but don't "fix" the Desktop backend's non-use — that's intentional since `docker sandbox run` manages its own image.
- **Credential persistence differs between backends** — Docker Desktop sandbox has a bespoke credential flow (symlinks + volume). Plain OCI needs explicit volume mounts at container creation time. Don't try to share the symlink-based approach; design credential handling in the OCI adapter independently.
- **Rootless detection is runtime-dependent** — `docker info` output format varies across Docker Engine versions and rootless configurations. Defensively handle missing or unexpected output; `rootless: None` (unknown) is a safe fallback.
- **Don't block on image registry** — Dockerfiles can be built and tested locally. The image publication pipeline is infrastructure work outside S02.
- **Patch targets for tests** — Per KNOWLEDGE.md, when mocking re-exported names, patch in the consumer's module namespace, not the definition site.

## Open Risks

- The Claude CLI installation process inside a plain OCI container is untested. Docker Desktop's `docker/sandbox-templates:claude-code` bundles everything; the SCC-owned image must replicate the correct Node.js version, Claude CLI version, and user/permissions setup. This may need iteration.
- Rootless Docker behavior with volume mounts and uid mapping differs from rootful Docker. The OCI backend should work in both modes, but edge cases in file ownership may surface during real testing.
- The OCI backend credential flow needs to work without the Docker Desktop sandbox volume symlink pattern. If the volume mount approach has timing issues, the detached → setup → exec pattern from the sandbox path should be adapted.