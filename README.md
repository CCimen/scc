<h1 align="center">SCC - Sandboxed Claude CLI</h1>

<p align="center">
  <a href="https://pypi.org/project/scc-cli/"><img src="https://img.shields.io/pypi/v/scc-cli?style=flat-square&label=PyPI" alt="PyPI"></a>
  <a href="https://pypi.org/project/scc-cli/"><img src="https://img.shields.io/pypi/pyversions/scc-cli?style=flat-square&label=Python" alt="Python"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-blue?style=flat-square" alt="License: MIT"></a>
  <a href="#contributing"><img src="https://img.shields.io/badge/Contributions-Welcome-brightgreen?style=flat-square" alt="Contributions Welcome"></a>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> ·
  <a href="#commands">Commands</a> ·
  <a href="#configuration">Configuration</a> ·
  <a href="docs/ARCHITECTURE.md">Architecture</a> ·
  <a href="#contributing">Contributing</a>
</p>

---

Run [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (Anthropic's AI coding CLI) in Docker sandboxes with organization-managed team profiles and git worktree support.

SCC isolates AI execution in containers, enforces branch safety, and prevents destructive git commands. Organizations distribute plugins through a central config—developers get standardized setups without manual configuration.

> **Plugin Marketplace:** Extend Claude with the [official plugin marketplace](https://github.com/CCimen/sandboxed-code-plugins). Start with [**scc-safety-net**](docs/MARKETPLACE.md#safety-net-plugin) to block destructive git commands like `push --force`.

## 30-Second Guide

**Requires:** Python 3.10+, Docker Desktop 4.50+, Git 2.30+

```bash
pip install scc-cli      # Install
scc setup                # Configure (paste your org URL, pick your team)
cd ~/project && scc      # Auto-detect workspace and launch (or scc start ~/project)
```

Run `scc doctor` to verify your environment or troubleshoot issues.

### Smart Start Flow

When you run `scc` or `scc start` from inside a git repository:
- **Auto-detects workspace** from your current directory
- **Shows Quick Resume** if you have recent sessions for this workspace
- **Prints brief context** (workspace name, branch, team) before launching

**Keyboard shortcuts in interactive mode:**
- `Enter` — Select/resume session
- `n` — Start new session
- `Esc` — Go back
- `q` — Quit

---

### Find Your Path

| You are... | Start here |
|------------|------------|
| **Developer** joining a team | [Developer Onboarding](#developer-onboarding) — what you get automatically |
| **Team Lead** setting up your team | [Team Setup](#team-setup) — manage plugins in your own repo |
| **Org Admin** configuring security | [Organization Setup](#organization-setup) — control what's allowed org-wide |
| Exploring **plugins** | [Plugin Marketplace](docs/MARKETPLACE.md) — official plugins & safety tools |

---

### Developer Onboarding

**New to a team?** After running `scc setup` and `scc start`, you get:

- **Your team's approved plugins and MCP servers** — pre-configured and ready
- **Organization security policies** — applied automatically, no action needed
- **Command guardrails** — block destructive git commands like `push --force` (when scc-safety-net plugin is enabled)
- **Isolated git worktrees** — your main branch stays clean while Claude experiments

**What you never need to do:**
- Edit config files manually
- Download or configure plugins
- Worry about security settings

Your org admin and team lead handle the configuration. You just code.

---

### Who Controls What

| Setting | Org Admin | Team Lead | Developer |
|---------|:---------:|:---------:|:---------:|
| Block dangerous plugins/servers | ✅ **Sets** | ❌ Cannot override | ❌ Cannot override |
| Default plugins for all teams | ✅ **Sets** | — | — |
| Team-specific plugins | ✅ Approves | ✅ **Chooses** | — |
| Project-local config (.scc.yaml) | ✅ Can restrict | ✅ Can restrict | ✅ **Extends** |
| Safety-net policy (block/warn) | ✅ **Sets** | ❌ Cannot override | ❌ Cannot override |

Organization security blocks cannot be overridden by teams or developers.

*"Approves" = teams can only select from org-allowed marketplaces; blocks always apply. "Extends" = can add plugins/settings, cannot remove org defaults.*

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
    "network_policy": "unrestricted"
  },
  "profiles": {
    "backend": { "additional_plugins": ["scc-safety-net@sandboxed-code-official"] },
    "frontend": { "additional_plugins": ["scc-safety-net@sandboxed-code-official"] }
  }
}
```

Host this anywhere: GitHub, GitLab, S3, or any HTTPS URL. Private repos work with token auth.

See [examples/](examples/) for complete org configs and [GOVERNANCE.md](docs/GOVERNANCE.md) for delegation rules.

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

## Commands

| Command | Description |
|---------|-------------|
| `scc` | Smart start: auto-detect workspace, show Quick Resume, or launch |
| `scc start` | Same as `scc` — auto-detects workspace from CWD |
| `scc start -i` | Force workspace picker (ignore current folder) |
| `scc start <path>` | Start Claude Code in sandbox for specific path |
| `scc start --resume` | Resume most recent session (no UI) |
| `scc start --select` | Show session picker to choose which session to resume |
| `scc start --standalone` | Launch without organization config (no team profile) |
| `scc start --offline` | Use cached org config only (no network) |
| `scc start --dry-run` | Preview launch configuration without starting container |
| `scc start --dry-run --json` | Output launch config as JSON (for CI/automation) |
| `scc start --non-interactive` | Fail fast instead of prompting (for CI/scripts) |
| `scc setup` | Configure organization connection |
| `scc stop` | Stop running sandbox(es) |
| `scc doctor` | Check system health |
| `scc team list` | List team profiles |
| `scc team switch <name>` | Switch to a different team |
| `scc config explain` | Show effective config with sources |
| `scc worktree create <repo> <name>` | Create git worktree |

Run `scc <command> --help` for options. See [CLI Reference](docs/CLI-REFERENCE.md) for full command list.

---

## Configuration

### Setup Modes

**Organization mode** (recommended):
```bash
scc setup
# Enter URL when prompted: https://gitlab.example.org/devops/scc-config.json
```

**Standalone mode** (no org config):
```bash
scc setup --standalone
```

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
~/.config/scc/config.json    # Org URL, team, preferences
~/.cache/scc/                # Cache (safe to delete)
<repo>/.scc.yaml             # Project-specific config
```

---

## Troubleshooting

Run `scc doctor` to diagnose issues.

| Problem | Solution |
|---------|----------|
| Docker not reachable | Start Docker Desktop |
| Organization config fetch failed | Check URL and token |
| Plugin blocked | Check `scc config explain` for security blocks |

See [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for more solutions.

---

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — system design, module structure
- [Governance](docs/GOVERNANCE.md) — delegation model, security boundaries
- [Marketplace](docs/MARKETPLACE.md) — plugin distribution and safety-net
- [Troubleshooting](docs/TROUBLESHOOTING.md) — common problems and solutions
- [Examples](examples/) — ready-to-use organization config templates

---

## Automation & CI

SCC supports non-interactive operation for CI/CD pipelines and scripting.

### Exit Codes

| Code | Name | Meaning |
|------|------|---------|
| 0 | `EXIT_SUCCESS` | Operation completed successfully |
| 1 | `EXIT_ERROR` | General error |
| 2 | `EXIT_USAGE` | Invalid command-line usage |
| 3 | `EXIT_CONFIG` | Configuration error |
| 4 | `EXIT_VALIDATION` | Validation failure |
| 5 | `EXIT_PREREQ` | Missing prerequisites |
| 6 | `EXIT_GOVERNANCE` | Blocked by security policy |
| 130 | `EXIT_CANCELLED` | User cancelled (Esc/Ctrl+C) |

### JSON Output

Use `--json` for machine-readable output:

```bash
# Preview launch configuration
scc start --dry-run --json

# List teams as JSON
scc team list --json

# Explain config with JSON envelope
scc config explain --json
```

JSON envelope format:
```json
{
  "apiVersion": "scc.cli/v1",
  "kind": "StartDryRun",
  "metadata": { "timestamp": "...", "version": "..." },
  "status": { "ok": true },
  "data": { ... }
}
```

### Non-Interactive Mode

Use `--non-interactive` to fail fast instead of prompting:

```bash
# CI pipeline: fail if workspace not specified
scc start --non-interactive ~/project

# Require explicit team selection
scc start --non-interactive --team backend ~/project

# Combine with JSON for full automation
scc start --dry-run --json --non-interactive ~/project
```

When `--non-interactive` is set:
- Missing required inputs cause immediate failure (exit 2)
- No TUI pickers or prompts are displayed
- Errors are returned as JSON when `--json` is also set

---

## Development

```bash
uv sync              # Install dependencies
uv run pytest        # Run tests
uv run ruff check    # Run linter
```

---

## License

MIT
