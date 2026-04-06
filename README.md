<h1 align="center">SCC — Sandboxed Coding CLI</h1>

<p align="center">
  <a href="https://pypi.org/project/scc-cli/"><img src="https://img.shields.io/pypi/v/scc-cli?style=flat-square&label=PyPI" alt="PyPI"></a>
  <a href="https://pypi.org/project/scc-cli/"><img src="https://img.shields.io/pypi/pyversions/scc-cli?style=flat-square&label=Python" alt="Python"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-blue?style=flat-square" alt="License: MIT"></a>
  <a href="#contributing"><img src="https://img.shields.io/badge/Contributions-Welcome-brightgreen?style=flat-square" alt="Contributions Welcome"></a>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> ·
  <a href="#why-teams-use-scc">Why SCC</a> ·
  <a href="#common-commands">Commands</a> ·
  <a href="#read-this-next">Read Next</a> ·
  <a href="https://scc-cli.dev">Documentation</a> ·
  <a href="https://scc-cli.dev/architecture/overview/">Architecture</a>
</p>

<p align="center">
  <strong>Full documentation:</strong> <a href="https://scc-cli.dev">scc-cli.dev</a>
</p>

---

SCC is a governed runtime for AI coding agents. It runs [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and [Codex](https://openai.com/index/introducing-codex/) inside OCI-compatible containers with provider-aware onboarding, team-managed configuration, runtime safety, network controls, and git worktree support.

SCC is not a new agent. It gives organizations an operating model for existing coding CLIs: one org config, delegated team ownership, repeatable developer onboarding, and a safer runtime that is easier to review and roll out across a company.

> The optional [scc-safety-net](https://scc-cli.dev/plugins/safety-net/) plugin adds extra agent-native git protection where supported. Today it is Claude-focused. SCC's built-in safety engine already protects both Claude and Codex inside the sandbox.

## Why Teams Use SCC

Teams use SCC when they want AI coding agents to feel operationally manageable instead of ad hoc.

- **Roll out one governed setup**: define org defaults once, then let team leads maintain team-level config within those boundaries.
- **Support more than one agent**: allow Claude, Codex, or both without rebuilding your workflow around a single vendor.
- **Onboard developers faster**: new developers run `scc setup` and get the approved package instead of manually installing plugins, hooks, MCP servers, and local rules.
- **Isolate the runtime**: run the agent in a container that sees the workspace you mounted, not your whole machine.
- **Control the network path**: keep egress open, force HTTP/HTTPS through a proxy sidecar, or lock the container down completely.
- **Apply runtime safety by default**: block destructive git commands and intercept explicit network tools inside the sandbox.
- **Keep daily workflows practical**: protected-branch prompts, session resume, dashboards, and worktree-based feature work are built in.

## Quick Start

**Requires:** Python 3.10+, Git 2.30+, and a Docker-compatible container runtime such as [Docker Engine](https://docs.docker.com/engine/), [OrbStack](https://orbstack.dev/), [Colima](https://github.com/abiosoft/colima), or [Docker Desktop](https://www.docker.com/products/docker-desktop/). Docker Desktop is supported, but not required.

```bash
uv tool install scc-cli
scc setup
cd ~/project && scc
```

What `scc setup` does:

- connects your org config or enables standalone mode
- connects Claude, Codex, or both
- stores your provider preference: `ask`, `claude`, or `codex`

What first launch does:

- resolves which provider to use
- checks readiness for auth and images
- builds the provider image if needed
- bootstraps provider auth if needed
- starts the agent inside a sandboxed container

Useful first checks:

```bash
scc doctor
scc doctor --provider codex
```

## How SCC Helps an Organization

SCC gives AI coding agents an organization-ready operating model.

| Role | What SCC gives them |
|---|---|
| **Org admin / platform team** | One central config for allowed providers, network policy, plugin/MCP governance, and defaults |
| **Team lead** | Delegated control over team-specific setup within org-approved boundaries |
| **Developer** | A repeatable onboarding flow and a ready-to-use sandboxed environment instead of manual local setup |

That combination is the main value: tighter control for the organization, less friction for the developer.

## What SCC Controls

| Surface | What SCC does |
|---|---|
| Providers | Runs Claude Code and Codex through one provider-neutral launch path |
| Filesystem | Mounts the workspace into the sandbox instead of exposing your whole machine |
| Network | Supports `open`, `web-egress-enforced`, and `locked-down-web` |
| Safety | Blocks destructive git commands and checks explicit network tools inside the container |
| Team config | Applies org and team settings consistently across developers |
| Plugins and MCP | Governs what is allowed, blocked, or injected into the runtime |
| Sessions | Supports start, resume, stop, inspect, and prune flows |
| Git workflows | Supports protected-branch prompts and worktree-based feature work |

One important point: a container alone does **not** solve network risk. If you care about what an agent can reach, use SCC's network policies, not just a default container runtime.

## Network and Safety

SCC separates sandboxing from egress control on purpose.

- `open`: unrestricted network access
- `web-egress-enforced`: the agent runs on an internal-only network and reaches HTTP/HTTPS through a Squid proxy sidecar with an ACL
- `locked-down-web`: the container runs with `--network=none`

The built-in safety engine is provider-neutral. It uses shell wrappers inside the image to evaluate commands before forwarding them to the real binary. In v1, the hard safety baseline focuses on destructive git commands and explicit network tools such as `curl`, `wget`, `ssh`, `scp`, `sftp`, and `rsync`.

Those runtime wrappers are defense-in-depth. They intercept risky commands inside the container, but the hard network boundary remains the runtime topology and proxy policy.

## Common Commands

```bash
# Start and resume
scc
scc start ~/project
scc start --provider codex ~/project
scc start --resume
scc start --select

# Provider management
scc provider show
scc provider set ask
scc provider set claude
scc provider set codex

# Sessions and containers
scc sessions
scc list
scc stop
scc stop --all
scc prune

# Worktrees
scc worktree . create feature-auth
scc worktree . enter feature-auth

# Diagnostics
scc doctor
scc config explain
scc support safety-audit
```

## Architecture at a Glance

SCC has three main parts:

- **Control plane**: provider selection, governance, config inheritance, readiness checks, and audit planning
- **Runtime backend**: OCI container launch, images, web egress topology, and sandbox lifecycle
- **Provider adapters**: Claude and Codex auth, settings rendering, runtime spec, and provider-specific startup behavior

That split keeps the core provider-neutral while letting each provider keep its own native details.

## Read This Next

If you only want to get productive, start here:

- [Quick Start](https://scc-cli.dev/getting-started/quick-start/)
- [Core Concepts](https://scc-cli.dev/getting-started/core-concepts/)
- [Daily Workflow](https://scc-cli.dev/guides/developer/daily-workflow/)

If you are evaluating SCC for a team or organization, read these next:

- [Architecture Overview](https://scc-cli.dev/architecture/overview/)
- [Security Model](https://scc-cli.dev/architecture/security-model/)
- [Governance Model](https://scc-cli.dev/architecture/governance-model/)
- [Examples](https://scc-cli.dev/examples/)
- [Plugin Marketplace](https://scc-cli.dev/plugins/marketplace/)

If you want command details:

- [CLI Reference](https://scc-cli.dev/reference/cli/overview/)
- [Troubleshooting](https://scc-cli.dev/troubleshooting/)

## Development

```bash
uv sync
uv run pytest
uv run ruff check
uv run mypy src/scc_cli
```

## Contributing

Issues, bug reports, docs fixes, and pull requests are welcome.

If you want to contribute:

- open an issue for bugs or product gaps
- open a PR for focused fixes
- keep user-facing claims truthful to the actual runtime behavior

## License

MIT
