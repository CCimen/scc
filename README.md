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
  <a href="https://scc-cli.dev">Documentation</a> ·
  <a href="#configuration">Configuration</a> ·
  <a href="https://scc-cli.dev/architecture/overview/">Architecture</a>
</p>

<p align="center">
  <strong>📚 Full Documentation: <a href="https://scc-cli.dev">scc-cli.dev</a></strong>
</p>

---

Run [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (Anthropic's AI coding CLI) in Docker sandboxes with organization-managed team profiles and git worktree support.

SCC isolates AI execution in containers, enforces branch safety, and prevents destructive git commands. Organizations distribute plugins through a central config—developers get standardized setups without manual configuration.

> **Plugin Marketplace:** Extend Claude with the [official plugin marketplace](https://github.com/CCimen/sandboxed-code-plugins). Start with [**scc-safety-net**](https://scc-cli.dev/plugins/safety-net/) to block destructive git commands like `push --force`.

## 30-Second Guide

**Requires:** Python 3.10+, Docker Desktop 4.50+, Git 2.30+

```bash
uv tool install scc-cli  # Install (recommended)
scc setup                # Configure (paste your org URL, pick your team)
cd ~/project && scc      # Auto-detect workspace and launch (or scc start ~/project)
```

> **Alternative:** `pip install scc-cli` works if you don't have [uv](https://docs.astral.sh/uv/).

Run `scc doctor` to verify your environment or troubleshoot issues.

### Smart Start Flow

When you run `scc` or `scc start`:
- **Auto-detects workspace** from git repository root or `.scc.yaml` location
- **Shows Quick Resume** if you have recent sessions for this workspace
- **Prints brief context** (workspace root, entry directory, team) before launching
- **Applies personal profile** (if saved) after team config, before workspace overrides
- **Bypass mode enabled**: Permission prompts are skipped by default since the Docker sandbox already provides isolation. Press `Shift+Tab` inside Claude to toggle permissions back on if needed
- **Safety guard**: Won't auto-launch from suspicious directories (home, `/tmp`). Explicit paths like `scc start ~/` prompt for confirmation

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
- **Command guardrails** — block destructive git commands like `push --force` (when scc-safety-net plugin is enabled)
- **Isolated git worktrees** — your main branch stays clean while Claude experiments
- **Personal profiles (optional)** — save your own plugin/MCP preferences per project

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
| Personal profiles (local) | ✅ Governed by security blocks | ✅ Governed by delegation | ✅ **Chooses** |
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
| `scc setup` | Configure organization connection |
| `scc doctor` | Check system health and diagnose issues |
| `scc stop` | Stop running sandbox(es) |

### Session & Team

| Command | Description |
|---------|-------------|
| `scc start --resume` | Resume most recent session |
| `scc start --select` | Pick from recent sessions |
| `scc team switch` | Switch to a different team profile |
| `scc sessions` | List recent sessions |

### Worktrees

| Command | Description |
|---------|-------------|
| `scc worktree create <repo> <name>` | Create git worktree for parallel development |
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
| `scc sessions prune` | Clean up old sessions |

### Governance & Admin

| Command | Description |
|---------|-------------|
| `scc config explain` | Show effective config with sources |
| `scc exceptions list` | View active exceptions |
| `scc audit plugins` | Audit installed plugins |
| `scc support bundle` | Generate support bundle for troubleshooting |
| `scc completion bash` | Generate shell completions (bash/zsh/fish) |

Run `scc <command> --help` for options. See **[CLI Reference](https://scc-cli.dev/reference/cli/overview/)** for the complete command list (40+ commands).

### Git Worktrees

**Primary method (no shell config needed):**

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

Run `scc config paths` to see all locations with sizes and permissions.

---

## Troubleshooting

Run `scc doctor` to diagnose issues.

| Problem | Solution |
|---------|----------|
| Docker not reachable | Start Docker Desktop |
| Organization config fetch failed | Check URL and token |
| Plugin blocked | Check `scc config explain` for security blocks |

See [Troubleshooting Guide](https://scc-cli.dev/troubleshooting/) for more solutions.

---

## Documentation

Visit **[scc-cli.dev](https://scc-cli.dev)** for comprehensive documentation:

- [Getting Started](https://scc-cli.dev/getting-started/quick-start/) — installation and first steps
- [CLI Reference](https://scc-cli.dev/reference/cli/overview/) — complete command reference (40+ commands)
- [Architecture](https://scc-cli.dev/architecture/overview/) — system design, module structure
- [Governance](https://scc-cli.dev/architecture/governance-model/) — delegation model, security boundaries
- [Plugin Marketplace](https://scc-cli.dev/plugins/marketplace/) — plugin distribution and safety-net
- [Troubleshooting](https://scc-cli.dev/troubleshooting/) — common problems and solutions
- [Examples](https://scc-cli.dev/examples/) — ready-to-use organization config templates

---

## Automation & CI

SCC supports non-interactive operation for CI/CD pipelines and scripting.

```bash
# CI pipeline example
scc start --non-interactive --team backend ~/project

# Preview configuration as JSON
scc start --dry-run --json

# Full automation mode
scc start --dry-run --json --non-interactive ~/project
```

**Key flags:**
- `--non-interactive` — Fail fast instead of prompting
- `--json` — Machine-readable output with standardized envelope
- `--dry-run` — Preview configuration without launching

**Exit codes:** 0 (success), 2 (usage error), 3 (config error), 4 (tool error), 5 (prerequisites), 6 (governance block), 130 (cancelled)

See [CLI Reference → Exit Codes](https://scc-cli.dev/reference/cli/overview/#exit-codes) for complete documentation.

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
