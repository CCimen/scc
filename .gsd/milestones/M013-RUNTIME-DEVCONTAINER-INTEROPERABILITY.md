# M013 - Runtime/Devcontainer Interoperability

## Purpose

Make SCC usable from a devcontainer or containerized development environment
without weakening SCC's governed runtime controls.

The first M013 slice proves the sibling-container model: SCC may run inside a
devcontainer, but it still creates its own governed OCI agent container. The
Docker daemon may need a host-side bind-mount source that differs from the path
visible to SCC inside the devcontainer.

## Non-goals

- Do not run the agent inside the existing devcontainer.
- Do not attach the agent container to arbitrary devcontainer or Compose service
  networks.
- Do not weaken `web-egress-enforced`, `locked-down-web`, safety wrappers, or
  provider launch preflight.
- Do not implement SSO, SCIM, SBOM/compliance bundle, project registry,
  enterprise dashboard, new providers, or Podman support in this milestone.
- Do not add broad compatibility paths for unshipped behavior.

## M013 Context

SCC's launch path currently assumes one path can serve two jobs:

- the logical workspace path SCC sees while resolving work context; and
- the path the Docker daemon can bind-mount into the agent container.

That holds when SCC runs on the host. It fails inside a devcontainer that talks
to the host Docker socket because SCC may see `/workspaces/app` while the host
daemon needs `/Users/name/app`.

M013 keeps WorkContext identity in the existing resolver and applies any host
path translation at launch planning time only. The target path and container
workdir remain the logical paths visible inside the agent container.

## Roadmap

| Slice | Status | Name | Scope | Done when |
| --- | --- | --- | --- | --- |
| S01 | Done | Host Docker workspace path mapping | Explicit `SCC_WORKSPACE_PATH_MAP=<container_path>:<host_path>` handling in launch planning, dry-run output, tests, and docs truth | SCC can plan a sibling OCI launch from a devcontainer without changing workdir or governance topology. |
| S02 | Done | Runtime diagnostics | Doctor evidence for devcontainer path-map readiness | Operators can diagnose missing, malformed, or non-matching host path mapping before launch. |
| S03 | Done | Real-runtime smoke | Optional Docker-marked smoke for mapped sibling-container launch | CI stays fake-runtime by default; real runtime is opt-in. |
| S04 | Done | Devcontainer network decision | Decide whether any devcontainer/Compose network bridge is safe and useful | Docs keep arbitrary devcontainer/Compose network attachment future/unsupported. |

## S01 Contract

`SCC_WORKSPACE_PATH_MAP` maps one logical container-visible prefix to the
host-visible prefix the Docker daemon can mount:

```bash
SCC_WORKSPACE_PATH_MAP=/workspaces/app:/Users/name/app
```

For a logical mount root equal to or under `/workspaces/app`, SCC uses the
matching host path as `MountSpec.source`. SCC keeps `MountSpec.target` and
`SandboxSpec.workdir` on the logical path so provider config and agent behavior
see the same workspace location the developer used.

Malformed, incomplete, relative, or non-matching maps are ignored. Dry-run output
must show the Docker mount source when it differs from the logical mount root.

## Tests

- Pure path-map tests for no map, direct map, nested map, malformed map, relative
  paths, and non-matching prefixes.
- Start-session tests proving translated `workspace_mount.source`,
  unchanged `workspace_mount.target`, unchanged workdir, and unchanged
  workspace-scoped provider config paths.
- Dry-run tests proving machine-readable output exposes the Docker mount source.
- Doctor tests proving missing, malformed, non-matching, and matching path maps
  produce actionable diagnostics.
- OCI runtime tests continue to prove container names differ by provider and are
  deterministic from the actual Docker mount source.
- Docs truth tests keep devcontainer claims scoped to this implemented behavior.
- Optional real-runtime smoke tests are marked `real_runtime` and require
  `SCC_REAL_RUNTIME_SMOKE=1`. They validate Docker bind mounting with
  `SCC_WORKSPACE_PATH_MAP` and `locked-down-web` command creation without making
  normal CI depend on Docker.

Run manually:

```bash
SCC_REAL_RUNTIME_SMOKE=1 \
SCC_REAL_RUNTIME_IMAGE=scc-agent-claude:latest \
uv run pytest -q --no-cov -m real_runtime
```

## Devcontainer Network Decision

M013 does not attach SCC agent containers to arbitrary devcontainer or Docker
Compose service networks.

That is deliberate. `web-egress-enforced` depends on SCC owning the agent
container's network topology: the agent is attached only to SCC's internal
network and reaches external destinations through the SCC proxy sidecar. Joining
an arbitrary project network would create another route and would need an
explicit policy model, audit record, and tests before it could be called a
governed runtime feature.

For v1, devcontainer interoperability means:

- SCC may run inside a devcontainer.
- SCC still launches a sibling governed OCI agent container.
- `SCC_WORKSPACE_PATH_MAP` bridges the host Docker socket bind-mount boundary.
- SCC network access remains controlled by `network_policy`.

Future service-network access should be designed as a separate governed
capability with named allowed networks, policy ownership, audit events, and
runtime smoke coverage.

## Peer Review

Claude peer loop was attempted first for M013 plan gate but the local account hit
its monthly spend limit. Antigravity reviewed the plan with blocking skepticism
and green-lit the narrowed S01 design:

- use one `SCC_WORKSPACE_PATH_MAP` variable instead of two variables;
- translate at launch planning, not workspace resolution;
- do not add a speculative identity field to `SandboxSpec`;
- keep OCI container naming bound to `workspace_mount.source`, which becomes the
  host-visible path when mapping is active;
- defer devcontainer/Compose network attachment to a separate decision.
