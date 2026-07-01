# M015 - Dev Environment Bridge MVP

## Purpose

Make SCC practical for projects that already use devcontainers or Docker Compose
without weakening SCC's governed runtime boundary.

M013 proved that SCC can run from a devcontainer and still launch a sibling SCC
agent container by translating the runtime mount source with
`SCC_WORKSPACE_PATH_MAP`. M015 builds on that baseline: SCC should help a coding
agent inspect or ask for approved project-service actions, while the agent
container never receives raw Docker socket access or arbitrary network
attachment to the project stack.

## Non-goals

- Do not run the agent inside the existing devcontainer.
- Do not mount `/var/run/docker.sock` into the agent container.
- Do not attach SCC agent containers to arbitrary devcontainer or Compose
  networks.
- Do not add free-form `docker`, `docker compose`, shell, or `exec` access.
- Do not create a project registry.
- Do not implement SSO, SCIM, SBOM/compliance bundle, enterprise dashboard,
  Podman support, or new providers in M015.
- Do not add public config schema or normalized models before a consuming
  command and behavior test exist.

## Current Baseline

- M012 golden journeys and docs claim lock are complete.
- M013 runtime/devcontainer interoperability is complete for the
  sibling-container path-map model.
- M014 enterprise identity is docs/planning-only; source behavior is not
  implemented.
- Source `main` and docs `main` are synced before M015 starts.

## M015 Context

Many real projects run databases, queues, local APIs, or test services through a
devcontainer or Compose stack. SCC's agent container should be able to understand
that environment and request approved support actions, but the enterprise
security posture must remain simple:

```text
developer host / SCC process
  owns Docker/devcontainer/Compose inspection and approved bridge actions

SCC agent container
  owns coding-agent execution inside SCC runtime
  does not own Docker socket, project service network, or arbitrary host shell
```

That keeps SCC explainable to municipalities, agencies, and companies: the
agent runtime is isolated, network policy remains SCC-owned, and every bridge
action can be traced to a named policy decision.

## Dev Bridge Architecture

M015 should reuse these existing owners:

| Concept | Canonical owner |
| --- | --- |
| Workspace identity | `src/scc_cli/application/workspace/use_cases.py` |
| Devcontainer host-path mapping | `src/scc_cli/core/runtime_mounts.py` |
| Launch/runtime mount planning | `src/scc_cli/application/start_session.py` |
| Runtime topology enforcement | `src/scc_cli/adapters/oci_sandbox_runtime.py` |
| Network topology enforcement | `src/scc_cli/adapters/egress_topology.py` |
| Operator readiness diagnostics | `src/scc_cli/doctor/checks/environment.py` |
| Raw config schema | `src/scc_cli/schemas/org-v1.schema.json` |
| Normalized typed config | `src/scc_cli/ports/config_models.py` |
| Config normalization | `src/scc_cli/services/config_normalizer.py` |
| Effective policy/explain decisions | `src/scc_cli/application/compute_effective_config.py` |
| Launch and safety audit evidence | existing audit/support application services |

Do not introduce a generic `DevEnvironmentManager`, plugin layer, runtime port,
or descriptor bag unless a real command needs it. The first code slice should be
read-only diagnostics over existing filesystem/runtime evidence.

## Threat Model

M015 must preserve these guarantees:

- Docker socket exposure: the agent container must not receive the host Docker
  socket as an ambient capability.
- Network bypass: project devcontainer or Compose networks must not create a
  second egress path around `web-egress-enforced` or `locked-down-web`.
- Arbitrary execution: the bridge must not become an unreviewed remote shell.
- Path spoofing: any path mapping must keep logical workspace identity separate
  from Docker-host-visible mount sources.
- Secret exposure: logs, health checks, and command output must be bounded and
  redactable before entering support bundles or audit artifacts.
- Audit evasion: every approved bridge action needs a stable event with policy,
  workspace, provider, and action identity.
- Config widening: project-local config may request narrower or named behavior,
  but it must not silently widen org/team policy.

## Roadmap

| Slice | Status | Name | Scope | Done when |
| --- | --- | --- | --- | --- |
| S00 | In progress | Source-of-truth reconciliation | Update stale milestone register, AGENTS guidance, D057, and this M015 file | Future agents see M015 as active and do not reopen D056 by accident. |
| S01 | Planned | Read-only dev environment diagnostics | Extend existing doctor diagnostics first; add a separate `scc dev` surface only if it earns its place | JSON/text output reports detected files, path-map readiness, Docker socket risk, and unsupported actions without mutating runtime state. |
| S02 | Planned | Named bridge action contract | Add the smallest public config/schema only after S01 identifies the command that consumes it | A named action can be represented without `dict[str, Any]`, arbitrary shell strings, or fake abstractions. |
| S03 | Planned | Approved command bridge | Let SCC host process run approved named actions with timeout, cwd bounds, audit, and redaction | Agent can request a named action; SCC denies unknown/free-form actions fail-closed. |
| S04 | Planned | Logs and health checks | Add bounded read-only service logs/health checks where policy allows | Output is size-limited, redactable, audited, and testable without Docker in normal CI. |
| S05 | Planned | Agent-facing JSON bridge surface | Expose deterministic machine-readable bridge status/results for Claude and Codex sessions | Provider adapters do not own bridge policy; artifacts remain SCC-owned. |
| S06 | Planned | Optional real-runtime smoke | Prove one approved bridge action against a real local dev stack behind an explicit marker | Normal CI remains fake-runtime; OrbStack/Docker smoke can run manually. |
| S07 | Planned | Docs truth update | Update public docs only for implemented bridge behavior | Docs claims map links every dev bridge claim to implementation and tests. |

## Recommended PR Slicing

1. PR 1: S00 planning/decision reconciliation only.
2. PR 2: S01 read-only diagnostics with tests and no new config schema.
3. PR 3: S02 typed named-action contract plus config/explain behavior.
4. PR 4: S03 approved command execution and audit.
5. PR 5: S04/S05 logs, health checks, agent-facing JSON, and docs.
6. PR 6: S06 optional real-runtime smoke if the fake-runtime bridge is stable.

## Exact First Implementation Slice

This PR is S00 only:

- mark M013 and M014 complete in `.gsd/PROJECT.md`;
- make M015 the active milestone in `.gsd/PROJECT.md` and `AGENTS.md`;
- record D057 in `.gsd/DECISIONS.md`;
- consolidate M015 roadmap/context/architecture/threat model/PR slicing here;
- do not add `dev_environment` schema, config models, command modules, or
  runtime code.

The first code PR should be S01. It should start with tests around a read-only
diagnostic surface. A good failing test is:

```text
Given a workspace with .devcontainer/devcontainer.json and compose.yaml,
and SCC_WORKSPACE_PATH_MAP is absent,
when the operator runs the dev-environment diagnostic in JSON mode,
then SCC reports detected dev-environment evidence, explains that the agent will
remain a sibling SCC container, reports missing path-map readiness, and states
that project-network attachment and Docker-socket access are unsupported.
```

## Validation Plan

For S00:

```bash
git diff --check
rg -n "M013 is the next planned|Runtime/devcontainer interoperability remains M013|M015 .*Enterprise Identity" AGENTS.md .gsd/PROJECT.md .gsd/DECISIONS.md
```

For S01 and later code slices:

```bash
uv run ruff check
uv run ruff format --check
uv run mypy src/scc_cli
uv run pytest -q --no-cov
git diff --check
```

If public docs change:

```bash
cd ../scc-cli-docs
bun run astro check
```

## Peer Review

Codex reviewed the M015 plan gate on 2026-07-01 and blocked schema/model work
until a consuming command exists. The accepted Ponytail shape is this planning
reconciliation slice first, followed by read-only diagnostics.
