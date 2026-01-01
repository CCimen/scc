# SCC CLI - Comprehensive UX/DX Analysis

> **Version**: 1.4.2
> **Generated**: January 2026
> **Purpose**: Complete documentation of all user flows, commands, and interactions

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Installation & First Run](#2-installation--first-run)
3. [Main Entry Point & Start Flow](#3-main-entry-point--start-flow)
4. [Interactive UI Components](#4-interactive-ui-components)
5. [Docker & Container Management](#5-docker--container-management)
6. [Git Worktree System](#6-git-worktree-system)
7. [Team & Organization Configuration](#7-team--organization-configuration)
8. [Setup & Configuration Commands](#8-setup--configuration-commands)
9. [Session & Context Management](#9-session--context-management)
10. [Doctor & Admin Commands](#10-doctor--admin-commands)
11. [Governance & Security](#11-governance--security)
12. [Marketplace & Plugin System](#12-marketplace--plugin-system)
13. [Git Safety Features](#13-git-safety-features)
14. [Keyboard Shortcuts Reference](#14-keyboard-shortcuts-reference)
15. [Exit Codes Reference](#15-exit-codes-reference)
16. [File Locations](#16-file-locations)

---

## 1. Executive Summary

### What is SCC?

**SCC (Sandboxed Claude CLI)** runs Claude Code in Docker sandboxes with:
- Organization-managed team profiles
- Git worktree support for parallel development
- Plugin marketplace with security governance
- Protected branch safety mechanisms

### Key Design Principles

1. **Developer Experience First** - Works out of the box with sensible defaults
2. **Safety by Default** - Protected branches, git hooks, sandbox isolation
3. **Team Configuration** - Centralized org policies, delegated team control
4. **No Manual Config** - Developers never edit config files manually

### Command Categories

| Category | Commands | Purpose |
|----------|----------|---------|
| **Session** | `scc`, `scc start`, `scc stop`, `scc list` | Launch and manage Claude sessions |
| **Configuration** | `scc setup`, `scc config`, `scc init` | Initial setup and configuration |
| **Team** | `scc team list`, `scc team switch` | Team profile management |
| **Worktree** | `scc worktree create/switch/list/remove` | Git worktree operations |
| **Admin** | `scc doctor`, `scc status`, `scc update` | System health and updates |
| **Governance** | `scc exceptions`, `scc unblock`, `scc audit` | Security policy management |

---

## 2. Installation & First Run

### Prerequisites

- Python 3.10+
- Docker Desktop 4.50+ (with sandbox feature)
- Git 2.30+

### Installation

```bash
pip install scc-cli      # Standard install
pipx install scc-cli     # Isolated install (recommended)
uv tool install scc-cli  # Fast install with uv
```

### First Run Experience

```bash
$ scc
# Detects first-time setup
# Auto-triggers setup wizard

┌─ Welcome to SCC ─────────────────────────────────────┐
│                                                       │
│  Do you have an organization config URL? [Y/n]       │
│                                                       │
│  Organization config URL: https://...                │
│                                                       │
│  Select your team profile:                           │
│    [1] backend - API services                        │
│    [2] frontend - React apps                         │
│    [3] platform - Infrastructure                     │
│                                                       │
│  Enable git hooks protection? [Y/n]                  │
│                                                       │
└───────────────────────────────────────────────────────┘

✓ Setup complete! Run 'scc start ~/project' to begin.
```

---

## 3. Main Entry Point & Start Flow

### Command: `scc` (No Arguments)

**Behavior depends on context:**

| Context | Action |
|---------|--------|
| In git repo + TTY | Smart Start → Quick Resume or launch |
| Not in repo + TTY | Dashboard with recent contexts |
| Non-TTY / CI | Error: requires explicit workspace |

### Command: `scc start [WORKSPACE] [OPTIONS]`

**Full Options:**

```
WORKSPACE              Path to workspace (optional, auto-detects CWD)

Session Options:
  -r, --resume         Resume most recent session (no prompt)
  -s, --select         Show session picker
  -t, --team NAME      Team profile to use
  --session NAME       Custom session name
  -w, --worktree NAME  Create worktree before starting

Launch Options:
  --fresh              Force new container
  --install-deps       Auto-install dependencies
  --offline            Use cached config only
  --standalone         No organization config

Output Options:
  --dry-run            Preview config without launching
  --json               JSON output
  --pretty             Pretty-print JSON
  --non-interactive    Fail if prompts needed
```

### Start Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    scc start [workspace]                     │
└──────────────────────────┬──────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
     No workspace    Workspace given    --resume/--select
          │                │                │
          ▼                ▼                ▼
   Interactive      Validate path      Session lookup
      Wizard             │                  │
          │              ▼                  │
          ▼         Quick Resume           │
   Team Selection    (if contexts)         │
          │              │                  │
          ▼              ▼                  │
   Workspace        Team Resolution ◄──────┘
    Selection            │
          │              ▼
          ▼         Git Safety Check
   Worktree?        (protected branch?)
          │              │
          └──────────────┼──────────────────┘
                         │
                         ▼
              Docker Sandbox Launch
                         │
                         ▼
               Claude Code Session
```

### Interactive Wizard Steps

**Step 0: Global Quick Resume** (if contexts exist)
- Shows recent work contexts
- Keyboard: `Enter` resume, `n` new, `Esc` back, `q` quit

**Step 1: Team Selection** (if org mode)
- List of available teams with descriptions
- Current team marked with checkmark

**Step 2: Workspace Selection**
- Current directory (if valid)
- Recent workspaces
- Team repositories
- Custom path
- Clone repository

**Step 2.5: Workspace-Scoped Quick Resume**
- Shows contexts for selected workspace only

**Step 3: Worktree Creation** (optional)
- Prompt: "Create worktree for isolated development?"
- Sanitizes name, creates `scc/` prefixed branch

**Step 4: Session Naming** (optional)
- Custom name for easy resume later

---

## 4. Interactive UI Components

### List Navigation (All Pickers)

| Key | Action |
|-----|--------|
| `↑` or `k` | Move cursor up |
| `↓` or `j` | Move cursor down |
| Type text | Filter items |
| `Backspace` | Delete filter char |
| `Enter` | Select item |
| `Esc` | Go back / cancel |
| `q` | Quit app |
| `t` | Switch team |
| `?` | Show help |

### Quick Resume Picker

| Key | Action | Result |
|-----|--------|--------|
| `Enter` | Resume | Returns selected context |
| `n` | New session | Continues to wizard |
| `Esc` | Back | Returns to previous screen |
| `q` | Quit | Exits entirely |

### Multi-Select Mode

| Key | Action |
|-----|--------|
| `Space` | Toggle selection |
| `a` | Toggle all |
| `Enter` | Confirm selection |

### Visual Indicators

| Symbol | Meaning |
|--------|---------|
| `@` | Current worktree |
| `✓` | Current team / selected |
| `●` | Container running |
| `○` | Container stopped |
| `★` | Current branch match |
| `📌` | Pinned context |

---

## 5. Docker & Container Management

### Container Lifecycle

```
┌──────────────────────────────────────────────────────────────┐
│              Detach → Symlink → Exec Pattern                  │
│                                                               │
│  1. docker sandbox run -d -w /path claude  → Container ID    │
│  2. docker exec <id> <symlink_script>      → Create symlinks │
│  3. docker exec -it <id> claude            → Run Claude       │
│                                                               │
│  (Solves OAuth credential persistence race condition)        │
└──────────────────────────────────────────────────────────────┘
```

### Container Commands

**List containers:**
```bash
scc list                    # All SCC containers
scc list -i                 # Interactive with actions
```

**Stop containers:**
```bash
scc stop                    # Stop with confirmation
scc stop <name>             # Stop specific
scc stop --all              # Stop all running
scc stop -i                 # Interactive multi-select
```

**Prune stopped:**
```bash
scc prune                   # Remove stopped containers
scc prune --dry-run         # Preview only
scc prune -y                # Skip confirmation
```

### Volume & Credential Persistence

- **Volume**: `docker-claude-sandbox-data`
- **Mount**: `/mnt/claude-data` in container
- **Credentials**: OAuth tokens persist across project switches
- **Settings**: Team plugins injected before launch

---

## 6. Git Worktree System

### Commands

```bash
# Create worktree
scc worktree create <repo> <name> [--base BRANCH] [--start]

# Switch to worktree
scc worktree switch <target>     # Fuzzy match
scc worktree switch ^            # Main branch
scc worktree switch -            # Previous directory

# Interactive selection
scc worktree select              # Pick existing worktree
scc worktree select --branches   # Include remote branches

# List worktrees
scc worktree list                # Basic list
scc worktree list -v             # With git status

# Remove worktree
scc worktree remove <repo> <name> [--force] [--yes]

# Clean stale entries
scc worktree prune [--dry-run]
```

### Shell Integration

Add to `~/.bashrc` or `~/.zshrc`:

```bash
wt() { cd "$(scc worktree switch "$@")" || return 1; }
```

**Usage:**
```bash
wt                  # Interactive picker
wt feature-auth     # Fuzzy match
wt ^                # Main branch
wt -                # Previous directory
```

### Status Symbols (list -v)

| Symbol | Meaning |
|--------|---------|
| `.` | Clean |
| `+N` | N staged |
| `!N` | N modified |
| `?N` | N untracked |
| `…` | Status timed out |

### Branch Naming

- Prefix: `scc/` (product namespace)
- Sanitization: lowercase, hyphens only
- Example: `feature/auth` → `scc/feature-auth`

---

## 7. Team & Organization Configuration

### Team Commands

```bash
scc team list              # Show available teams
scc team list --sync       # Force refresh from remote
scc team switch            # Interactive picker
scc team switch <name>     # Direct switch
scc team info <name>       # Team details
scc team validate <name>   # Validate effective plugins
```

### Organization Commands

```bash
scc org validate <path>    # Validate org config file
scc org status             # Show org connection status
scc org update             # Refresh org config
scc org update --team X    # Refresh team X config
scc org update --all-teams # Refresh all federated teams
```

### Configuration Hierarchy

```
Organization Defaults (blocked_plugins, enabled_plugins)
         │
         ▼
    Team Profile (additional_plugins, disabled_plugins)
         │
         ▼
    Project Config (.scc.yaml - additional_plugins)
         │
         ▼
    Security Blocks (FINAL - cannot be overridden)
         │
         ▼
    Effective Configuration
```

### Plugin Resolution (5-Step)

1. **Normalize** all plugin references
2. **Merge** defaults + team additional
3. **Apply** team disabled patterns
4. **Filter** by team allowed patterns (additional only)
5. **Block** by org security patterns (final gate)

---

## 8. Setup & Configuration Commands

### Setup Wizard

```bash
scc setup                  # Interactive wizard
scc setup --standalone     # No organization config
scc setup --reset          # Clear all config
scc setup --org github:owner/repo --team backend  # Non-interactive
```

**Wizard Steps:**
1. Organization URL (or standalone)
2. Authentication (if 401)
3. Team selection
4. Git hooks enablement

### Config Commands

```bash
scc config show            # Display current config
scc config get <key>       # Get specific value
scc config set <key> <val> # Set value
scc config edit            # Open in $EDITOR
scc config explain         # Show effective config with sources
```

### Project Init

```bash
scc init                   # Create .scc.yaml in CWD
scc init ~/project         # Create in specific path
scc init --force           # Overwrite existing
```

**Template:**
```yaml
additional_plugins: []
session:
  timeout_hours: 8
# mcp_servers: []
# env: {}
```

---

## 9. Session & Context Management

### Session Tracking

**Storage:** `~/.config/scc/sessions.json`

**Keyed by:** workspace + branch combination

**Commands:**
```bash
scc sessions               # List recent sessions
scc start --resume         # Resume most recent
scc start --select         # Pick from recent
```

### Context Tracking (Quick Resume)

**Storage:** `~/.cache/scc/contexts.json`

**Data:**
- Team
- Repository root
- Worktree path
- Branch name
- Last session ID
- Pinned status

**Sorting:** Pinned first, then by recency

### Workspace Team Pinning

**Storage:** `workspace_team_map` in config.json

**Behavior:**
- Remembers last team used for each workspace
- Auto-suggests on next visit
- Override with `--team` flag

---

## 10. Doctor & Admin Commands

### Doctor Command

```bash
scc doctor                 # Full health check
scc doctor --quick         # Single-line status
scc doctor --json          # JSON output
scc doctor ~/project       # Check specific workspace
```

**Checks Performed:**

| Category | Checks |
|----------|--------|
| **Environment** | Git, Docker, Docker Daemon, Sandbox, WSL2 |
| **Configuration** | Config directory, User config validity |
| **Organization** | Org config reachable, Marketplace auth |
| **Cache** | Cache readable, TTL status, Migration |
| **State** | Exception stores, Proxy environment |

**Output:**
```
┌─ System Health Check ─────────────────────────┐
│ Status │ Check            │ Details           │
├────────┼──────────────────┼───────────────────┤
│   ✓    │ Git              │ git version 2.42  │
│   ✓    │ Docker           │ Docker 27.0.0     │
│   ✓    │ Docker Daemon    │ Running           │
│   ✓    │ Docker Sandbox   │ Available         │
│   ✓    │ Config Directory │ Writable          │
└─────────────────────────────────────────────────┘

All prerequisites met! Ready to run Claude Code.
```

### Status Command

```bash
scc status                 # Quick overview
scc status --verbose       # Include delegation details
scc status --json          # JSON output
```

### Statusline Command

```bash
scc statusline --install   # Install git info statusline
scc statusline --show      # Show current config
scc statusline --uninstall # Remove statusline
```

**Display Format:**
```
Model | 🌿 main | ⎇ feature:my-feature | Ctx 42% | $0.15
```

### Stats Command

```bash
scc stats                  # Show usage stats
scc stats --days 7         # Last 7 days
scc stats export --json    # Export as JSON
scc stats aggregate *.json # Combine multiple exports
```

### Update Command

```bash
scc update                 # Check for updates
scc update --force         # Bypass throttling
```

---

## 11. Governance & Security

### Exception System

**Two-Layer Model:**

| Layer | Scope | Override Type | Approval |
|-------|-------|---------------|----------|
| **Policy** | Security + Delegation | PR-approved | Org admin |
| **Local** | Delegation only | Self-serve | Developer |

### Commands

```bash
# List exceptions
scc exceptions list              # Active only
scc exceptions list --all        # Include expired
scc exceptions list --expired    # Expired only

# Create exception
scc exceptions create \
  --allow-plugin my-plugin \
  --ttl 8h \
  --reason "Sprint demo"

# Generate policy PR snippet
scc exceptions create --policy \
  --id INC-2025-123 \
  --allow-plugin blocked-tool \
  --reason "Incident response"

# Quick unblock (delegation only)
scc unblock my-plugin --ttl 8h --reason "Testing"

# Delete exception
scc exceptions delete <id>

# Cleanup expired
scc exceptions cleanup

# Reset stores
scc exceptions reset --user --yes
```

### Security Invariants

1. **Security blocks immutable locally** - Only policy exceptions can override
2. **All exceptions time-bounded** - No indefinite overrides
3. **Expiration always enforced** - Checked on every evaluation
4. **Audit trail required** - Reason mandatory for governance ops

### Audit Command

```bash
scc audit plugins          # Validate installed plugins
scc audit plugins --json   # JSON output for CI
```

---

## 12. Marketplace & Plugin System

### Plugin Discovery Flow

```
Org Config → Team Profile → Effective Plugins → Materialize Marketplaces
     │              │               │                    │
     └──────────────┴───────────────┴────────────────────┘
                                │
                                ▼
                    Claude Code settings.local.json
```

### Plugin Reference Formats

```
name@marketplace       # Canonical: code-review@internal
@marketplace/name      # npm-style: @internal/code-review
name                   # Bare: auto-resolves if unambiguous
```

### Marketplace Sources

| Type | Configuration |
|------|---------------|
| **GitHub** | owner, repo, branch, path |
| **Git** | url, branch, path |
| **URL** | url, headers |
| **Directory** | local path |

### Safety-Net Plugin

**Blocks destructive commands:**
- `git push --force`
- `git reset --hard`
- `git branch -D`
- `git stash drop/clear`
- `git clean -f`
- `git checkout -- <file>`

**Configuration:**
```json
{
  "security": {
    "safety_net": {
      "action": "block"  // block, warn, or allow
    }
  }
}
```

---

## 13. Git Safety Features

### Protected Branches

**Default protected:** `main`, `master`, `develop`, `production`, `staging`

**Safety prompt when on protected branch:**
```
╭─ Protected Branch ──────────────────────────────────╮
│ You are on branch 'main'                            │
│                                                     │
│ [1] Create branch (recommended)                     │
│ [2] Continue (pushes blocked)                       │
│ [3] Cancel                                          │
╰─────────────────────────────────────────────────────╯
```

### Git Hooks

**Pre-push hook blocks:**
- Direct push to protected branches
- Provides guidance for feature branch workflow

**Installation:**
- Opt-in via `scc setup`
- Repo-local only (never global)
- Non-destructive (won't overwrite user hooks)

### Non-Git Directory Handling

**When workspace is not a git repo:**
1. Prompt: "Initialize git?"
2. If declined: Continue without worktree features

**When repo has no commits:**
1. Prompt: "Create empty initial commit?"
2. Required for worktree creation

---

## 14. Keyboard Shortcuts Reference

### Universal (All Modes)

| Key | Action |
|-----|--------|
| `↑` / `k` | Move up |
| `↓` / `j` | Move down |
| Type | Filter |
| `Backspace` | Delete filter char |
| `?` | Show help |

### Picker Mode

| Key | Action |
|-----|--------|
| `Enter` | Select |
| `Esc` | Back/Cancel |
| `q` | Quit |
| `t` | Switch team |

### Multi-Select Mode

| Key | Action |
|-----|--------|
| `Space` | Toggle selection |
| `a` | Toggle all |
| `Enter` | Confirm |

### Quick Resume Mode

| Key | Action |
|-----|--------|
| `Enter` | Resume selected |
| `n` | New session |
| `Esc` | Go back |
| `q` | Quit |

### Dashboard Mode

| Key | Action |
|-----|--------|
| `Tab` | Next tab |
| `Shift+Tab` | Previous tab |
| `r` | Refresh |
| `n` | New session |
| `Enter` | View details |

---

## 15. Exit Codes Reference

| Code | Name | Meaning |
|------|------|---------|
| 0 | SUCCESS | Operation completed |
| 1 | ERROR | General error |
| 2 | USAGE | Invalid usage |
| 3 | CONFIG | Configuration error |
| 4 | VALIDATION | Validation failure |
| 5 | PREREQ | Missing prerequisites |
| 6 | GOVERNANCE | Blocked by policy |
| 130 | CANCELLED | User cancelled |

---

## 16. File Locations

### User Configuration

```
~/.config/scc/
├── config.json          # Org URL, team, preferences
├── sessions.json        # Session history
└── exceptions.json      # User-scoped exceptions
```

### Cache (Regenerable)

```
~/.cache/scc/
├── org_config.json      # Cached org config
├── cache_meta.json      # ETags, timestamps
├── contexts.json        # Quick Resume contexts
├── update_check_meta.json
└── usage.jsonl          # Usage statistics
```

### Project-Level

```
<repo>/
├── .scc.yaml            # Project config (optional)
├── .scc/
│   └── exceptions.json  # Repo-scoped exceptions
└── .scc-marketplaces/   # Materialized plugins
```

### Docker

```
Volume: docker-claude-sandbox-data
├── settings.json        # Injected settings
├── .credentials.json    # OAuth tokens
├── credentials.json     # API keys
└── effective_policy.json # Safety-net policy (read-only)
```

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│                    SCC Quick Reference                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  GETTING STARTED                                             │
│    scc setup            Initial configuration                │
│    scc doctor           Check system health                  │
│    scc                   Smart start (auto-detect)           │
│                                                              │
│  DAILY WORKFLOW                                              │
│    scc start ~/project  Start Claude in project              │
│    scc start --resume   Resume last session                  │
│    scc stop             Stop running containers              │
│                                                              │
│  WORKTREE WORKFLOW                                           │
│    wt                   Switch worktree (shell function)     │
│    wt ^                 Switch to main branch                │
│    wt feature-x         Fuzzy match worktree                 │
│    scc worktree list -v Show status                          │
│                                                              │
│  TEAM MANAGEMENT                                             │
│    scc team list        Show teams                           │
│    scc team switch      Change team                          │
│    scc config explain   Show effective config                │
│                                                              │
│  TROUBLESHOOTING                                             │
│    scc doctor           Diagnose issues                      │
│    scc config explain   See what's blocked                   │
│    scc exceptions list  View active overrides                │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

*This document was generated from comprehensive codebase analysis for SCC CLI v1.4.2*
