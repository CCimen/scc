<h1 align="center">SCC — Sandboxed Coding CLI</h1>

<p align="center">
  <a href="https://pypi.org/project/scc-cli/"><img src="https://img.shields.io/pypi/v/scc-cli?style=flat-square&label=PyPI" alt="PyPI"></a>
  <a href="https://pypi.org/project/scc-cli/"><img src="https://img.shields.io/pypi/pyversions/scc-cli?style=flat-square&label=Python" alt="Python"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-blue?style=flat-square" alt="License: MIT"></a>
  <a href="#contributing"><img src="https://img.shields.io/badge/Contributions-Welcome-brightgreen?style=flat-square" alt="Contributions Welcome"></a>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> ·
  <a href="#commands">Commands</a> ·
  <a href="https://scc-cli.dev">Documentation</a> ·
  <a href="#configuration">Configuration</a> ·
  <a href="https://scc-cli.dev/architecture/overview/">Architecture</a>
</p>

<p align="center">
  <strong>📚 Full Documentation: <a href="https://scc-cli.dev">scc-cli.dev</a></strong>
</p>

---

Run AI coding agents ([Claude Code](https://docs.anthropic.com/en/docs/claude-code), [Codex](https://openai.com/index/introducing-codex/)) in container sandboxes with organization-managed team profiles, runtime safety, and git worktree support.

SCC is a **provider-neutral governed runtime**. It isolates agent execution in OCI containers, enforces web egress policy through network topology, runs a fail-closed safety engine, and distributes team configuration through a central org config — developers get standardized setups without manual configuration, regardless of which agent they use.

> **Plugin Marketplace:** Extend your agent with the [official plugin marketplace](https://github.com/CCimen/sandboxed-code-plugins). Start with [**scc-safety-net**](https://scc-cli.dev/plugins/safety-net/) for additional git command protection beyond the built-in safety engine. The plugin is Claude-focused today; Codex support is planned, while SCC's built-in safety engine already protects both providers.

## Quick Start

**Requires:** Python 3.10+, a container runtime ([Docker Engine](https://docs.docker.com/engine/), [OrbStack](https://orbstack.dev/), [Colima](https://github.com/abiosoft/colima), or [Docker Desktop](https://www.docker.com/products/docker-desktop/)), Git 2.30+

```bash
uv tool install scc-cli  # Install (recommended)
scc setup                # Configure org, connect providers (Claude, Codex, or both)
cd ~/project && scc      # Auto-detect workspace and launch
```

> **Alternative:** `pip install scc-cli` works if you don't have [uv](https://docs.astral.sh/uv/).

Run `scc doctor` to verify your environment. Use `scc doctor --provider codex` to check a specific provider.

### Provider Setup

During `scc setup`, SCC connects your agent providers:

- **Claude Code** — authenticates via Anthropic's browser sign-in flow
- **Codex** — authenticates via OpenAI's browser sign-in flow (localhost callback)

You can connect one or both. SCC stores your **provider preference**:
- `ask` — prompt every time (default when both are connected)
- `claude` — always use Claude Code
- `codex` — always use Codex

```bash
scc provider show          # Show current preference
scc provider set ask       # Prompt every time
scc provider set claude    # Always use Claude Code
scc provider set codex     # Always use Codex
```

The `--provider` flag on `scc start` overrides the preference for a single session:

```bash
scc start --provider codex ~/project
```

SCC also remembers the last-used provider per workspace, so repeated launches in the same project default to the provider you used last time.
When the global preference is `ask`, SCC still prompts if multiple providers are viable and uses workspace context only to preselect a sensible default.

### Smart Start Flow

When you run `scc` or `scc start`:
1. **Auto-detects workspace** from git repository root or `.scc.yaml` location
2. **Resolves provider** — uses the CLI flag first, resumes with the original session provider when applicable, then applies your saved preference and workspace context before prompting if multiple providers are still viable
3. **Checks readiness** — verifies the provider image exists and auth is valid (auto-builds image or triggers auth if needed)
4. **Shows Quick Resume** if you have recent sessions for this workspace
5. **Prints brief context** (workspace root, entry directory, team, provider) before launching
6. **Starts a sandboxed container** with your team's configuration

- **Permission bypass**: Permission prompts are skipped by default inside the sandbox since the container already provides isolation. Press `Shift+Tab` inside Claude to toggle permissions back on if needed.
- **Safety guard**: Won't auto-launch from suspicious directories (home, `/tmp`). Explicit paths like `scc start ~/` prompt for confirmation.
- **Protected branch prompt**: If you're on `main` or `master`, SCC shows a speed bump and offers to create a feature branch or continue with push protection enabled.

### Session Lifecycle

SCC manages the full lifecycle — not just starting sessions:

```bash
scc                        # Smart start (auto-detect, Quick Resume)
scc start ~/project        # Start in a specific directory
scc start --resume         # Resume the most recent session
scc start --select         # Pick from recent sessions interactively
scc sessions               # List recent sessions
scc list                   # List all running SCC containers
scc status                 # Show current configuration and state
scc stop                   # Stop a running sandbox (interactive picker)
scc stop --all             # Stop all running sandboxes
scc prune                  # Remove stopped SCC containers
```

**Sandbox conflict handling:** If a sandbox already exists for your workspace:
- **Stale sandbox** (stopped) — automatically replaced
- **Live sandbox** (running) — SCC prompts: keep the existing session, replace it, or cancel
- **Force new** — use `scc start --fresh` to always create a new container

**Keyboard shortcuts in dashboard:**
- `↑↓` — Navigate list
- `Enter` — Open action menu (containers/sessions/worktrees)
- `Tab` — Switch between tabs
- `n` — Start new session
- `t` — Switch team
- `p` — Profile quick menu (save/apply/diff)
- `r` — Refresh
- `s` — Settings & maintenance
- `?` — Help
- `q` — Quit

---

### Find Your Path

| You are... | Start here |
|------------|------------|
| **Developer** joining a team | [Developer Onboarding](#developer-onboarding) — what you get automatically |
| **Team Lead** setting up your team | [Team Setup](#team-setup) — manage plugins in your own repo |
| **Org Admin** configuring security | [Organization Setup](#organization-setup) — control what's allowed org-wide |
| Exploring **plugins** | [Plugin Marketplace](https://scc-cli.dev/plugins/marketplace/) — official plugins & safety tools |

---

### Developer Onboarding

**New to a team?** After running `scc setup` and `scc start`, you get:

- **Your team's approved plugins and MCP servers** — pre-configured and ready
- **Organization security policies** — applied automatically, no action needed
- **Built-in safety engine** — SCC's core safety engine blocks destructive git commands (`push --force`, `reset --hard`, `branch -D`, etc.) and intercepts explicit network tools (curl, wget, ssh, scp, sftp, rsync) inside containers. The safety engine is fail-closed: if policy cannot be loaded, all guarded commands are blocked. The optional scc-safety-net plugin provides additional coverage via agent-native hooks.
- **Isolated git worktrees** — your main branch stays clean while the agent experiments
- **Personal profiles (optional)** — save your own plugin/MCP preferences per project
- **Provider choice** — use Claude Code, Codex, or both, governed by team policy

**What you never need to do:**
- Edit config files manually
- Download or configure plugins
- Worry about security settings
- Build container images (SCC auto-builds on first run)

Your org admin and team lead handle the configuration. You just code.

---

### Who Controls What

| Setting | Org Admin | Team Lead | Developer |
|---------|:---------:|:---------:|:---------:|
| Block dangerous plugins/servers | ✅ **Sets** | ❌ Cannot override | ❌ Cannot override |
| Default plugins for all teams | ✅ **Sets** | — | — |
| Team-specific plugins | ✅ Approves | ✅ **Chooses** | — |
| Project-local config (.scc.yaml) | ✅ Can restrict | ✅ Can restrict | ✅ **Extends** |
| Personal profiles (local) | ✅ Governed by security blocks | ✅ Governed by delegation | ✅ **Chooses** |
| Safety-net policy (block/warn) | ✅ **Sets** | ❌ Cannot override | ❌ Cannot override |
| Allowed providers | ✅ **Sets** | ❌ Cannot override | ✅ **Chooses** from allowed |

Organization security blocks cannot be overridden by teams or developers.

*"Approves" = teams can only select from org-allowed marketplaces; blocks always apply. "Extends" = can add plugins/settings, cannot remove org defaults.*

### Enforcement Scope (v1)

- SCC enforces org-managed plugins and MCP servers at runtime.
- MCP servers in repo `.mcp.json` or plugin bundles are outside SCC enforcement scope (block the plugin to restrict).
- **Network policy enforcement:**
  - `open` — no egress restriction; the agent has unrestricted network access.
  - `web-egress-enforced` — topology-based isolation: the agent container is placed on an internal-only Docker network and can only reach the internet through a Squid proxy sidecar. The proxy enforces an ACL for HTTP/HTTPS traffic. Enforcement is IPv4-only in v1; raw TCP/UDP beyond HTTP(S) is not filtered.
  - `locked-down-web` — the container runs with `--network=none`. No external network access at all.
- **Runtime safety:** SCC's built-in safety engine intercepts destructive git commands and explicit network tools (curl, wget, ssh, scp, sftp, rsync) inside the container via shell wrappers. The wrappers are defense-in-depth — network topology and proxy policy remain the hard egress control. Safety policy is fail-closed: if policy cannot be loaded, all guarded commands are blocked.
- `session.auto_resume` is advisory only in v1.
- **Provider plugin model:** Claude Code and Codex have different native plugin, rules, and hook surfaces. SCC unifies governance at the approval and bundle layer — it does not pretend they share an identical plugin format. Each provider's native configuration is rendered by a provider-specific adapter.

---

### Container Images

SCC owns a set of container images that provide the sandboxed runtime:

| Image | Purpose |
|-------|---------|
| `scc-base` | Base image with safety wrappers, the standalone safety evaluator, and shared tooling |
| `scc-agent-claude` | Claude Code agent image (extends scc-base) |
| `scc-agent-codex` | Codex agent image (extends scc-base) |
| `scc-egress-proxy` | Squid proxy sidecar for `web-egress-enforced` network policy |

**First-run behavior:** The first time you start a session with a provider, SCC automatically builds the required image from bundled Dockerfiles. This takes a few minutes. Subsequent launches use the cached image.

**Manual build** (if needed):

```bash
docker build -t scc-agent-claude:latest images/scc-agent-claude/
docker build -t scc-agent-codex:latest images/scc-agent-codex/
```

Run `scc doctor --provider claude` or `scc doctor --provider codex` to check image availability. If the image is missing, doctor shows the exact build command.

Each provider gets its own persistent Docker volume for credential and data persistence (e.g., `docker-claude-sandbox-data`, `docker-codex-sandbox-data`). Provider containers are identity-isolated — running Claude and Codex in the same workspace produces separate containers with separate volumes.

### Container Runtime Support

SCC works with any Docker-compatible container runtime:

| Runtime | Status | Notes |
|---------|--------|-------|
| [Docker Engine](https://docs.docker.com/engine/) | ✅ Supported | Standard Docker daemon |
| [OrbStack](https://orbstack.dev/) | ✅ Supported | Fast, lightweight macOS alternative |
| [Colima](https://github.com/abiosoft/colima) | ✅ Supported | Open-source Docker on macOS/Linux |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | ✅ Supported | Full GUI experience |
| [Podman](https://podman.io/) | 🔄 Planned | Not yet fully validated — architecture supports it |

SCC auto-detects the available runtime. Docker Desktop is **not** required.

---

### Organization Setup

Org admins create a single JSON config that controls security for all teams:

```json
{
  "schema_version": "1.0.0",
  "organization": { "name": "Acme Corp", "id": "acme" },
  "marketplaces": {
    "sandboxed-code-official": {
      "source": "github",
      "owner": "CCimen",
      "repo": "sandboxed-code-plugins"
    }
  },
  "security": {
    "blocked_plugins": ["*malicious*"],
    "blocked_mcp_servers": ["*.untrusted.com"],
    "safety_net": { "action": "block" }
  },
  "defaults": {
    "allowed_plugins": ["*"],
    "network_policy": "open"
  },
  "profiles": {
    "backend": { "additional_plugins": ["scc-safety-net@sandboxed-code-official"] },
    "frontend": { "additional_plugins": ["scc-safety-net@sandboxed-code-official"] }
  }
}
```

Host this anywhere: GitHub, GitLab, S3, or any HTTPS URL. Private repos work with token auth.

See [examples/](examples/) for complete org configs and [Governance](https://scc-cli.dev/architecture/governance-model/) for delegation rules.

---

### Team Setup

Teams can manage their plugins **two ways**:

**Option A: Inline (simple)** — Team config lives in the org config file.
```json
"profiles": {
  "backend": {
    "additional_plugins": ["scc-safety-net@sandboxed-code-official"]
  }
}
```

**Option B: Team Repo (GitOps)** — Team maintains their own config repo.
```json
"profiles": {
  "backend": {
    "config_source": {
      "source": "github",
      "owner": "acme",
      "repo": "backend-team-scc-config"
    }
  }
}
```

With Option B, team leads can update plugins via PRs to their own repo—no org admin approval needed for allowed additions.

**Config precedence:** Org defaults → Team profile → Project `.scc.yaml` (additive merge; blocks apply after merge).

---

### Personal Profiles

Want your own plugins or MCP servers without committing anything? Personal profiles are per‑project, stored outside the repo, and auto‑applied on `scc start`.

If you install plugins inside the container and they only show up in sandbox settings, `scc profile save` and `scc profile status` will detect them and offer to import them into `.claude/settings.local.json` before saving.

```bash
# Save current workspace preferences
scc profile save

# Apply or preview
scc profile apply
scc profile apply --preview

# Check status/drift
scc profile status
```

**TUI Integration:** Press `p` in the dashboard or go to **Settings → Profiles** for visual profile management:
- Save/Apply/Diff profiles without CLI commands
- **Sync profiles** overlay for export/import to a local folder
- Import preview shows what will change before applying

**Sync across machines:**

```bash
# Via TUI: Settings → Profiles → Sync profiles
# Or via CLI with git operations:
scc profile export --repo ~/dotfiles/scc-profiles --commit --push
scc profile sync --repo ~/dotfiles/scc-profiles --pull --commit --push
```

> **Note:** TUI sync writes files locally only (no git). Use CLI flags `--commit --push` for git operations.

---

## Commands

### Essential Commands

| Command | Description |
|---------|-------------|
| `scc` | Smart start: auto-detect workspace, show Quick Resume, or launch |
| `scc setup` | Configure organization connection and provider auth |
| `scc doctor` | Check system health and diagnose issues |
| `scc doctor --provider codex` | Check readiness for a specific provider |
| `scc stop` | Stop running sandbox(es) |
| `scc status` | Show current configuration and state |

### Provider Management

| Command | Description |
|---------|-------------|
| `scc provider show` | Show currently selected provider preference |
| `scc provider set <pref>` | Set global preference (`ask`, `claude`, or `codex`) |
| `scc start --provider <id>` | Override provider for a single session |

### Session & Team

| Command | Description |
|---------|-------------|
| `scc start --resume` | Resume most recent session |
| `scc start --select` | Pick from recent sessions |
| `scc start --fresh` | Force a new container (replace existing) |
| `scc team switch` | Switch to a different team profile |
| `scc sessions` | List recent sessions |
| `scc list` | List all running SCC containers |
| `scc prune` | Remove stopped SCC containers |

### Worktrees

| Command | Description |
|---------|-------------|
| `scc worktree create <repo> <name>` | Create git worktree and auto-start agent session |
| `scc worktree create <repo> <name> --no-start` | Create worktree without starting a session |
| `scc worktree enter [target]` | Enter worktree in subshell (no shell config needed) |
| `scc worktree list -v` | List worktrees with git status |

### Personal Profiles

| Command | Description |
|---------|-------------|
| `scc profile save` | Save current workspace settings as a personal profile |
| `scc profile apply` | Apply profile to current workspace |
| `scc profile diff` | Show diff between profile and workspace |
| `scc profile status` | Show whether a profile exists and if drift is detected |
| `scc profile export --repo PATH` | Export profiles to a local repo |
| `scc profile import --repo PATH` | Import profiles from a local repo |
| `scc profile sync --repo PATH` | Pull/import + export + optional commit/push |

### Maintenance

| Command | Description |
|---------|-------------|
| `scc reset` | Interactive maintenance hub (cache, sessions, config) |
| `scc reset --cache` | Clear cache files |
| `scc reset --sessions` | Prune old sessions (keeps recent 20) |
| `scc reset --all` | Factory reset (removes all SCC data) |
| `scc config paths` | Show file locations and sizes |

### Governance & Admin

| Command | Description |
|---------|-------------|
| `scc config explain` | Show effective config with sources |
| `scc exceptions list` | View active exceptions |
| `scc audit plugins` | Audit installed plugins |
| `scc support bundle` | Generate support bundle for troubleshooting |
| `scc support launch-audit` | Inspect recent launch diagnostics |
| `scc support safety-audit` | Inspect recent safety-check audit events |
| `scc completion bash` | Generate shell completions (bash/zsh/fish) |

Run `scc <command> --help` for options. See **[CLI Reference](https://scc-cli.dev/reference/cli/overview/)** for the complete command list (40+ commands).

### Git Worktrees

Worktrees let you run multiple agent sessions on different branches without conflicts.

**Creating worktrees:**

```bash
scc worktree create ~/project feature-auth          # Create + auto-start agent
scc worktree create ~/project feature-auth --no-start  # Create only, start later
```

**Entering worktrees (no shell config needed):**

```bash
scc worktree enter feature-auth   # Opens a subshell in the worktree
# Type 'exit' to return to your previous directory
```

**Power users:** Add this shell wrapper for seamless `cd` switching:

```bash
# Add to ~/.bashrc or ~/.zshrc
wt() {
  local p
  p="$(scc worktree switch "$@")" || return $?
  cd "$p" || return 1
}
```

**Usage examples (both methods):**

```bash
scc worktree enter ^        # Enter main branch worktree
scc worktree enter -        # Enter previous worktree (like cd -)
wt feature-auth             # Switch with shell wrapper
wt scc/feature-x            # Match by full branch name
```

**Protected branch behavior:** When starting a session on `main` or `master`, SCC shows a visual speed bump warning and offers to create a feature branch instead. If you continue on the protected branch, git push hooks block direct pushes.

**Note:** Branch names with `/` are sanitized to `-` (e.g., `feature/auth` → `feature-auth`).

**Status indicators in `list -v`:**

| Symbol | Meaning |
|--------|---------|
| `+N` | N staged files |
| `!N` | N modified files |
| `?N` | N untracked files |
| `.` | Clean worktree |
| `…` | Status timed out |

**Cleanup stale entries:**

```bash
scc worktree prune -n   # Dry-run: show what would be pruned
scc worktree prune      # Actually prune stale entries
```

---

## Configuration

### Setup Modes

**Organization mode** (recommended):
```bash
scc setup
# Enter URL when prompted: https://gitlab.example.org/devops/scc-config.json
# Connect providers: Claude Code, Codex, or both
# Set provider preference: ask, claude, or codex
```

**Standalone mode** (no org config):
```bash
scc setup --standalone
```

### Provider Preference

```bash
scc provider show          # Show current preference
scc provider set ask       # Prompt when multiple providers are available
scc provider set claude    # Default to Claude Code
scc provider set codex     # Default to Codex
```

Provider resolution order: explicit `--provider` > resumed session provider > global `ask` prompt when multiple providers are viable > workspace last-used context > global preference > single viable provider auto-selection.

### Project Config

Add `.scc.yaml` to your repository root for project-specific settings:

```yaml
additional_plugins:
  - "project-linter@internal"

session:
  timeout_hours: 4
```

### File Locations

```
~/.config/scc/config.json      # Org URL, team, provider preference
~/.cache/scc/                   # Cache (safe to delete)
<repo>/.scc.yaml                # Project-specific config
<repo>/.scc/config.local.json   # Workspace-local state (last-used provider, gitignored)
```

Run `scc config paths` to see all locations with sizes and permissions.

---

## Architecture

SCC is designed as a **provider-neutral governed runtime**. The architecture separates shared infrastructure from provider-specific adapters:

**Shared core** (provider-neutral):
- Safety engine (shell tokenizer, git rules, network tool rules — fail-closed)
- Web egress topology (internal Docker network + Squid proxy sidecar)
- Audit sink (durable JSONL for launch and safety events)
- Bundle resolver and renderer pipeline
- Preflight readiness checks

**Provider adapters** (provider-specific):
- `AgentProvider` protocol — capability metadata, auth check, launch spec, bootstrap
- `AgentRunner` — settings serialization in provider-native format
- Provider-specific container images, config directories, and credential volumes

The `ProviderRuntimeSpec` registry maps each provider to its runtime constants (image ref, config dir, settings path, data volume). Adding a new provider means adding one registry entry and one adapter — the core is untouched.

> **Future providers:** The architecture is designed for extensibility. Support for additional providers (e.g., [OpenCode](https://github.com/nicholasgriffintn/opencode)) is planned but not yet shipped. Claude Code and Codex are the two currently supported providers.

See [Architecture](https://scc-cli.dev/architecture/overview/) for the full design documentation.

---

## Troubleshooting

Run `scc doctor` to diagnose issues (includes safety-policy and provider image health checks). Use `scc doctor --provider codex` to check a specific provider.

For recent launch failures, run `scc support launch-audit` to inspect launch diagnostics. For safety-related diagnostics, run `scc support safety-audit`.

**Provider readiness states** (shown by `scc doctor` and `scc setup`):

| State | Meaning |
|-------|---------|
| **Launch-ready** | Both auth and image are present — ready to start |
| **Auth cache present** | Auth credentials exist but image needs building |
| **Image available** | Container image exists but auth is missing |
| **Sign-in needed** | Neither auth nor image — run `scc setup` to connect |

| Problem | Solution |
|---------|----------|
| Container runtime not reachable | Start Docker Engine, OrbStack, Colima, or Docker Desktop |
| Provider image missing | SCC auto-builds on first start, or run `docker build -t scc-agent-<provider> images/scc-agent-<provider>/` |
| Auth missing or expired | Run `scc setup` to re-authenticate, or SCC will trigger browser sign-in on next start |
| Codex auth callback failed | Ensure port 1455 is free (Codex uses localhost:1455 for OAuth callback) |
| Organization config fetch failed | Check URL and token |
| Plugin blocked | Check `scc config explain` for security blocks |

See [Troubleshooting Guide](https://scc-cli.dev/troubleshooting/) for more solutions.

---

## Documentation

Visit **[scc-cli.dev](https://scc-cli.dev)** for comprehensive documentation:

- [Getting Started](https://scc-cli.dev/getting-started/quick-start/) — installation and first steps
- [CLI Reference](https://scc-cli.dev/reference/cli/overview/) — complete command reference (40+ commands)
- [Architecture](https://scc-cli.dev/architecture/overview/) — provider-neutral design, runtime model
- [Governance](https://scc-cli.dev/architecture/governance-model/) — delegation model, security boundaries
- [Plugin Marketplace](https://scc-cli.dev/plugins/marketplace/) — plugin distribution and safety-net
- [Troubleshooting](https://scc-cli.dev/troubleshooting/) — common problems and solutions
- [Examples](https://scc-cli.dev/examples/) — ready-to-use organization config templates

---

## Automation & CI

SCC supports non-interactive operation for CI/CD pipelines and scripting.

```bash
# CI pipeline example
scc start --non-interactive --provider claude --team backend ~/project

# Preview configuration as JSON
scc start --dry-run --json --provider codex

# Full automation mode
scc start --dry-run --json --non-interactive ~/project
```

**Key flags:**
- `--non-interactive` — Fail fast instead of prompting
- `--provider <id>` — Specify provider explicitly (required in CI when both are available)
- `--json` — Machine-readable output with standardized envelope
- `--dry-run` — Preview configuration without launching

**Exit codes:** 0 (success), 2 (usage error), 3 (config error), 4 (tool error), 5 (prerequisites), 6 (governance block), 130 (cancelled)

See [CLI Reference → Exit Codes](https://scc-cli.dev/reference/cli/overview/#exit-codes) for complete documentation.

---

## Development

```bash
uv sync              # Install dependencies
uv run pytest        # Run tests (5100+ tests)
uv run ruff check    # Run linter
uv run mypy src/scc_cli  # Type check (303 files)
```

---

## License

MIT
