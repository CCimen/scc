# CLI Reference

Complete command reference for SCC (Sandboxed Claude CLI).

**Audience:** Users and operators
**Related docs:** [README](../README.md) | [Troubleshooting](TROUBLESHOOTING.md) | [Governance](GOVERNANCE.md)

---

## Table of Contents

- [Global Options](#global-options)
- [Getting Started](#getting-started)
  - [setup](#scc-setup)
  - [init](#scc-init)
  - [doctor](#scc-doctor)
- [Core Workflow](#core-workflow)
  - [start](#scc-start)
  - [stop](#scc-stop)
  - [status](#scc-status)
- [Session Management](#session-management)
  - [sessions](#scc-sessions)
  - [context](#scc-context)
- [Worktree Management](#worktree-management)
  - [worktree create](#scc-worktree-create)
  - [worktree list](#scc-worktree-list)
  - [worktree enter](#scc-worktree-enter)
  - [worktree switch](#scc-worktree-switch)
  - [worktree select](#scc-worktree-select)
  - [worktree remove](#scc-worktree-remove)
  - [worktree prune](#scc-worktree-prune)
- [Team Management](#team-management)
  - [team list](#scc-team-list)
  - [team current](#scc-team-current)
  - [team switch](#scc-team-switch)
  - [team info](#scc-team-info)
  - [team validate](#scc-team-validate)
- [Configuration](#configuration)
  - [config](#scc-config)
  - [statusline](#scc-statusline)
  - [update](#scc-update)
- [Governance & Security](#governance--security)
  - [exceptions list](#scc-exceptions-list)
  - [exceptions create](#scc-exceptions-create)
  - [exceptions delete](#scc-exceptions-delete)
  - [exceptions cleanup](#scc-exceptions-cleanup)
  - [exceptions reset](#scc-exceptions-reset)
  - [unblock](#scc-unblock)
  - [audit plugins](#scc-audit-plugins)
- [Organization Management](#organization-management)
  - [org validate](#scc-org-validate)
  - [org update](#scc-org-update)
  - [org status](#scc-org-status)
  - [org import](#scc-org-import)
  - [org templates](#scc-org-templates)
- [Administration](#administration)
  - [stats](#scc-stats)
  - [support bundle](#scc-support-bundle)
  - [prune](#scc-prune)
- [Exit Codes](#exit-codes)

---

## Global Options

These options are available on all commands:

| Option | Description |
|--------|-------------|
| `--debug` | Show detailed error information for troubleshooting |
| `--version`, `-v` | Show version and exit |
| `--help`, `-h` | Show help for any command |

---

## Getting Started

Commands for initial setup and health checks.

### scc setup

Configure SCC with your organization settings.

```
scc setup [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `-q`, `--quick` | Quick setup with defaults |
| `--reset` | Reset configuration to defaults |
| `--org SOURCE` | Organization source (URL or shorthand like `github:org/repo`) |
| `-p`, `--profile PROFILE` | Profile/team to select |
| `-t`, `--team TEAM` | Team profile to select (alias for `--profile`) |
| `--auth SPEC` | Auth specification (`env:VAR` or `command:CMD`) |
| `--standalone` | Standalone mode without organization config |
| `--non-interactive` | Fail fast instead of prompting |

**Examples:**

```bash
# Interactive setup wizard
scc setup

# Quick setup with organization URL
scc setup --org https://example.org/scc-config.json --team backend

# Standalone mode (no organization)
scc setup --standalone

# Reset and reconfigure
scc setup --reset
```

---

### scc init

Initialize project-specific configuration (`.scc.yaml`).

```
scc init [PATH] [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `PATH` | Target directory (default: current directory) |

**Options:**

| Option | Description |
|--------|-------------|
| `-f`, `--force` | Overwrite existing `.scc.yaml` without prompting |
| `-y`, `--yes` | Skip confirmation prompts |
| `--json` | Output as JSON |
| `--pretty` | Pretty-print JSON output |

**Examples:**

```bash
# Initialize in current directory
scc init

# Initialize in specific directory
scc init ~/projects/my-app

# Force overwrite existing config
scc init --force
```

---

### scc doctor

Run health checks to diagnose issues.

```
scc doctor [WORKSPACE] [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `WORKSPACE` | Optional workspace path to check |

**Options:**

| Option | Description |
|--------|-------------|
| `-q`, `--quick` | Quick status only (skip detailed checks) |
| `--json` | Output as JSON |
| `--pretty` | Pretty-print JSON output |

**Examples:**

```bash
# Full health check
scc doctor

# Quick status check
scc doctor --quick

# Check specific workspace
scc doctor ~/projects/my-app

# JSON output for CI
scc doctor --json
```

**See also:** [Troubleshooting → Doctor Checks](TROUBLESHOOTING.md#doctor-checks)

---

## Core Workflow

Primary commands for daily use.

### scc start

Launch Claude Code in a sandboxed Docker container.

```
scc start [WORKSPACE] [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `WORKSPACE` | Path to workspace (auto-detected from current directory if omitted) |

**Options:**

| Option | Description |
|--------|-------------|
| `-t`, `--team TEAM` | Team profile to use (session-only, doesn't change default) |
| `--session NAME` | Session name for identification |
| `-r`, `--resume` | Resume most recent session |
| `-s`, `--select` | Interactive picker to select from recent sessions |
| `-i`, `--interactive` | Force interactive workspace picker |
| `--fresh` | Force new container (don't resume existing) |
| `-w`, `--worktree NAME` | Create worktree with this name before starting |
| `--install-deps` | Install dependencies before starting |
| `--offline` | Use cached config only (error if none cached) |
| `--standalone` | Run without organization config |
| `--dry-run` | Preview resolved configuration without launching |
| `--json` | Output as JSON (useful with `--dry-run`) |
| `--pretty` | Pretty-print JSON output |
| `--non-interactive` | Fail fast if interactive input required |

**Examples:**

```bash
# Smart start (auto-detect workspace)
scc

# Start in specific directory
scc start ~/projects/my-app

# Resume most recent session
scc start --resume

# Select from recent sessions
scc start --select

# Use different team for this session
scc start --team security ~/project

# Preview launch configuration
scc start --dry-run --json

# CI/automation mode
scc start --non-interactive --team backend ~/project
```

**Keyboard shortcuts in interactive mode:**

| Key | Action |
|-----|--------|
| `Enter` | Select/resume session |
| `n` | Start new session |
| `Esc` | Go back |
| `q` | Quit |

---

### scc stop

Stop running Claude Code sandbox(es).

```
scc stop [CONTAINER] [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `CONTAINER` | Container name or ID (interactive picker if omitted) |

**Options:**

| Option | Description |
|--------|-------------|
| `-a`, `--all` | Stop all running Claude Code sandboxes |
| `-i`, `--interactive` | Use multi-select picker to choose containers |
| `-y`, `--yes` | Skip confirmation prompt |

**Examples:**

```bash
# Interactive picker
scc stop

# Stop specific container
scc stop claude-my-project-abc123

# Stop all sandboxes
scc stop --all

# Stop all without confirmation
scc stop --all --yes
```

---

### scc status

Show current SCC configuration status.

```
scc status [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `-v`, `--verbose` | Show detailed information |
| `--json` | Output as JSON envelope |
| `--pretty` | Pretty-print JSON output |

**Examples:**

```bash
# Quick status
scc status

# Detailed status
scc status --verbose
```

---

## Session Management

Commands for managing work sessions and contexts.

### scc sessions

List recent sessions (alias: `scc session list`).

```
scc sessions [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `-n`, `--limit N` | Number of sessions to show (default: 10) |
| `-s`, `--select` | Interactive picker to select a session |

**Examples:**

```bash
# List recent sessions
scc sessions

# Show more sessions
scc sessions --limit 20

# Interactive session picker
scc sessions --select
```

---

### scc context

Manage work contexts (team + workspace associations).

#### scc context clear

Clear stored work contexts.

```
scc context clear [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `-y`, `--yes` | Skip confirmation prompt |

---

## Worktree Management

Commands for parallel development with git worktrees.

### scc worktree create

Create a new worktree for parallel development.

```
scc worktree create <WORKSPACE> <NAME> [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `WORKSPACE` | Path to the main repository |
| `NAME` | Name for the worktree/feature |

**Options:**

| Option | Description |
|--------|-------------|
| `-b`, `--base BRANCH` | Base branch (default: current branch) |
| `--start` / `--no-start` | Start Claude after creating (default: `--start`) |
| `--install-deps` | Install dependencies after creating worktree |

**Examples:**

```bash
# Create worktree and start session
scc worktree create ~/project feature-auth

# Create from specific branch
scc worktree create ~/project bugfix-123 --base main

# Create without starting Claude
scc worktree create ~/project experiment --no-start
```

**Note:** Branch names with `/` are sanitized to `-` (e.g., `feature/auth` → `feature-auth`).

---

### scc worktree list

List all worktrees for a repository.

```
scc worktree list [WORKSPACE] [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `WORKSPACE` | Path to the repository (default: current directory) |

**Options:**

| Option | Description |
|--------|-------------|
| `-i`, `--interactive` | Interactive mode: select a worktree to work with |
| `-v`, `--verbose` | Show git status (staged/modified/untracked) |
| `--json` | Output as JSON |
| `--pretty` | Pretty-print JSON output |

**Status indicators in verbose mode:**

| Symbol | Meaning |
|--------|---------|
| `+N` | N staged files |
| `!N` | N modified files |
| `?N` | N untracked files |
| `.` | Clean worktree |
| `…` | Status timed out |

**Examples:**

```bash
# List worktrees
scc worktree list

# List with git status
scc worktree list -v

# Interactive picker
scc worktree list -i
```

---

### scc worktree enter

Enter a worktree in a new subshell (no shell config needed).

```
scc worktree enter [TARGET] [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `TARGET` | Worktree name, `-` (previous), `^` (main branch), or fuzzy match |

**Options:**

| Option | Description |
|--------|-------------|
| `-w`, `--workspace PATH` | Path to the repository (default: current directory) |

**Examples:**

```bash
# Enter by name
scc worktree enter feature-auth

# Enter main branch worktree
scc worktree enter ^

# Enter previous worktree (like cd -)
scc worktree enter -

# Type 'exit' to return to previous directory
```

---

### scc worktree switch

Switch to a worktree (outputs path for shell wrapper integration).

```
scc worktree switch [TARGET] [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `TARGET` | Worktree name, `-` (previous), `^` (main branch), or fuzzy match |

**Options:**

| Option | Description |
|--------|-------------|
| `-w`, `--workspace PATH` | Path to the repository (default: current directory) |

**Shell wrapper (add to ~/.bashrc or ~/.zshrc):**

```bash
wt() {
  local p
  p="$(scc worktree switch "$@")" || return $?
  cd "$p" || return 1
}
```

---

### scc worktree select

Interactive worktree picker.

```
scc worktree select [WORKSPACE] [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `WORKSPACE` | Path to the repository (default: current directory) |

**Options:**

| Option | Description |
|--------|-------------|
| `-b`, `--branches` | Include branches without worktrees |

---

### scc worktree remove

Remove a worktree.

```
scc worktree remove <WORKSPACE> <NAME> [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `WORKSPACE` | Path to the main repository |
| `NAME` | Name of the worktree to remove |

**Options:**

| Option | Description |
|--------|-------------|
| `-f`, `--force` | Force removal even with uncommitted changes |
| `-y`, `--yes` | Skip all confirmation prompts |
| `--dry-run` | Show what would be removed without removing |

---

### scc worktree prune

Clean stale worktree entries from git.

```
scc worktree prune [WORKSPACE] [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `WORKSPACE` | Path to the repository (default: current directory) |

**Options:**

| Option | Description |
|--------|-------------|
| `-n`, `--dry-run` | Show what would be pruned without pruning |

**Examples:**

```bash
# Preview what would be pruned
scc worktree prune -n

# Actually prune stale entries
scc worktree prune
```

---

## Team Management

Commands for managing team profiles.

### scc team list

List available team profiles.

```
scc team list [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `-v`, `--verbose` | Show full descriptions |
| `-s`, `--sync` | Sync team configs from organization |
| `--json` | Output as JSON envelope |
| `--pretty` | Pretty-print JSON output |

---

### scc team current

Show the currently selected team.

```
scc team current [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--json` | Output as JSON envelope |
| `--pretty` | Pretty-print JSON output |

---

### scc team switch

Switch to a different team profile.

```
scc team switch [TEAM_NAME] [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `TEAM_NAME` | Team name (interactive picker if not provided) |

**Options:**

| Option | Description |
|--------|-------------|
| `--non-interactive` | Fail if team name not provided |
| `--json` | Output as JSON envelope |
| `--pretty` | Pretty-print JSON output |

---

### scc team info

Show detailed information about a team.

```
scc team info <TEAM_NAME> [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `TEAM_NAME` | Team name to show details for |

**Options:**

| Option | Description |
|--------|-------------|
| `--json` | Output as JSON envelope |
| `--pretty` | Pretty-print JSON output |

---

### scc team validate

Validate team configuration against organization policies.

```
scc team validate <TEAM_NAME> [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `TEAM_NAME` | Team name to validate |

**Options:**

| Option | Description |
|--------|-------------|
| `-v`, `--verbose` | Show detailed validation output |
| `--json` | Output as JSON envelope |
| `--pretty` | Pretty-print JSON output |

---

## Configuration

Commands for managing SCC configuration.

### scc config

Manage SCC configuration.

```
scc config [ACTION] [KEY] [VALUE] [OPTIONS]
```

**Actions:**

| Action | Description |
|--------|-------------|
| `set KEY VALUE` | Set a configuration value |
| `get KEY` | Get a specific value |
| `show` | Show all configuration |
| `edit` | Open config in editor |
| `explain` | Explain effective configuration with sources |

**Options:**

| Option | Description |
|--------|-------------|
| `--show` | Show current config |
| `--edit` | Open config in editor |
| `--field FIELD` | Filter explain output to specific field |
| `--workspace PATH` | Workspace path for project config context |

**Examples:**

```bash
# Show current configuration
scc config show

# Explain where settings come from
scc config explain

# Explain specific field
scc config explain --field plugins

# Edit configuration
scc config edit
```

**See also:** [Governance → Configuration Layers](GOVERNANCE.md#configuration-layers)

---

### scc statusline

Configure Claude Code status line integration.

```
scc statusline [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `-i`, `--install` | Install the SCC status line script |
| `--uninstall` | Remove the status line configuration |
| `-s`, `--show` | Show current status line config |

---

### scc update

Check for CLI updates.

```
scc update [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `-f`, `--force` | Force check even if recently checked |

---

## Governance & Security

Commands for managing security policies and exceptions.

### scc exceptions list

View active and expired exceptions.

```
scc exceptions list [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--active` | Show only active (non-expired) exceptions |
| `--expired` | Show only expired exceptions |
| `--all` | Show all exceptions (active and expired) |
| `--json` | Output as JSON |

---

### scc exceptions create

Create a new exception to unblock a plugin, MCP server, or image.

```
scc exceptions create [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--policy` | Generate YAML snippet for policy PR (instead of local exception) |
| `--id ID` | Exception ID (required for `--policy`) |
| `--ttl TTL` | Time-to-live (e.g., `8h`, `30m`, `1d`) |
| `--expires-at TIME` | Expiration time (RFC3339 format) |
| `--until TIME` | Expire at time of day (HH:MM format) |
| `--reason TEXT` | Reason for exception (required) |
| `--allow-mcp SERVER` | Allow MCP server (repeatable) |
| `--allow-plugin PLUGIN` | Allow plugin (repeatable) |
| `--allow-image IMAGE` | Allow base image (repeatable) |
| `--shared` | Save to repo store instead of user store |

**Examples:**

```bash
# Create 8-hour exception for an MCP server
scc exceptions create --allow-mcp jira-api --ttl 8h --reason "Sprint demo"

# Create exception until end of day
scc exceptions create --allow-plugin debug-tool --until 18:00 --reason "Debugging session"

# Generate policy exception for PR
scc exceptions create --policy --id security-audit-2024 --allow-plugin scanner
```

**See also:** [Governance → Exceptions](GOVERNANCE.md#exceptions)

---

### scc exceptions delete

Remove an exception by ID.

```
scc exceptions delete <EXCEPTION_ID> [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `EXCEPTION_ID` | Exception ID or unambiguous prefix |

**Options:**

| Option | Description |
|--------|-------------|
| `-y`, `--yes` | Skip confirmation |

---

### scc exceptions cleanup

Prune expired exceptions.

```
scc exceptions cleanup
```

---

### scc exceptions reset

Clear all exception stores.

```
scc exceptions reset [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `-y`, `--yes` | Skip confirmation |
| `--user` | Reset only user store |
| `--repo` | Reset only repo store |

---

### scc unblock

Quick shortcut to create an exception.

```
scc unblock <TARGET> [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `TARGET` | Plugin, MCP server, or image to unblock |

**Options:**

| Option | Description |
|--------|-------------|
| `--ttl TTL` | Time-to-live (default from policy) |
| `--reason TEXT` | Reason for unblocking |
| `--shared` | Save to repo store instead of user store |

**Examples:**

```bash
# Quick unblock for 8 hours
scc unblock my-plugin --ttl 8h --reason "Testing"
```

---

### scc audit plugins

Audit installed Claude Code plugins.

```
scc audit plugins [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--json` | Output as JSON with schemaVersion for CI integration |

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0 | All plugins parsed successfully (or no plugins installed) |
| 1 | One or more plugins have malformed or unreadable manifests |

**Examples:**

```bash
# Human-readable audit
scc audit plugins

# JSON output for CI
scc audit plugins --json
```

---

## Organization Management

Commands for organization administrators.

### scc org validate

Validate organization configuration.

```
scc org validate [SOURCE] [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `SOURCE` | Config source (URL, file path, or shorthand) |

**Options:**

| Option | Description |
|--------|-------------|
| `--json` | Output as JSON |
| `--pretty` | Pretty-print JSON output |

---

### scc org update

Update organization configuration.

```
scc org update [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--team NAME` | Refresh specific team's cached config |
| `--all-teams` | Refresh all federated team configs |
| `-f`, `--force` | Force update even if cache is fresh |

---

### scc org status

Show organization configuration status.

```
scc org status [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--json` | Output as JSON |
| `--pretty` | Pretty-print JSON output |

---

### scc org import

Import organization configuration from a source.

```
scc org import <SOURCE> [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `SOURCE` | Config source (URL, file path, or shorthand like `github:org/repo`) |

---

### scc org templates

List available organization configuration templates.

```
scc org templates [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--json` | Output as JSON |

---

## Administration

Commands for system administration.

### scc stats

View and export usage statistics.

```
scc stats [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--days N` | Limit to last N days |

**Subcommands:**

| Subcommand | Description |
|------------|-------------|
| `export` | Export statistics as JSON |
| `aggregate` | Combine multiple export files |

**Examples:**

```bash
# View usage summary
scc stats

# Last 7 days only
scc stats --days 7

# Export for aggregation
scc stats export --json > stats.json

# Aggregate multiple exports
scc stats aggregate team1.json team2.json
```

---

### scc support bundle

Generate a support bundle for troubleshooting.

```
scc support bundle [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `-o`, `--output PATH` | Output path for the bundle zip file |
| `--json` | Output manifest as JSON instead of creating zip |
| `--pretty` | Pretty-print JSON output |
| `--no-redact-paths` | Don't redact home directory paths |

**Examples:**

```bash
# Generate support bundle
scc support bundle

# Save to specific location
scc support bundle -o ~/Desktop/scc-support.zip

# JSON manifest only
scc support bundle --json
```

**Note:** Secrets and sensitive paths are automatically redacted.

---

### scc prune

Remove stopped containers and clean up resources.

```
scc prune [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `-y`, `--yes` | Skip confirmation prompt |
| `--dry-run` | Only show what would be removed |

---

## Exit Codes

All SCC commands use consistent exit codes:

| Code | Constant | Meaning |
|------|----------|---------|
| 0 | `EXIT_SUCCESS` | Operation completed successfully |
| 1 | `EXIT_ERROR` | General/unexpected error |
| 2 | `EXIT_USAGE` | Invalid usage/arguments |
| 3 | `EXIT_CONFIG` | Configuration or network error |
| 4 | `EXIT_TOOL` | External tool failed (git, docker) |
| 5 | `EXIT_PREREQ` | Prerequisites not met (Docker, Git not installed) |
| 6 | `EXIT_GOVERNANCE` | Blocked by governance policy |
| 130 | `EXIT_CANCELLED` | User cancelled (Esc/Ctrl+C) |

---

## JSON Output

Commands with `--json` support output a standardized envelope:

```json
{
  "apiVersion": "scc.cli/v1",
  "kind": "CommandName",
  "metadata": {
    "generatedAt": "2025-12-23T10:00:00Z",
    "cliVersion": "1.5.0"
  },
  "status": {
    "ok": true,
    "errors": [],
    "warnings": []
  },
  "data": { }
}
```

Use `--pretty` for human-readable formatting, or pipe to `jq` for processing:

```bash
scc start --dry-run --json | jq '.data.plugins'
```

---

## See Also

- [README](../README.md) — Quick start and overview
- [Architecture](ARCHITECTURE.md) — System design and module structure
- [Governance](GOVERNANCE.md) — Security policies and delegation
- [Marketplace](MARKETPLACE.md) — Plugin ecosystem
- [Troubleshooting](TROUBLESHOOTING.md) — Common problems and solutions
