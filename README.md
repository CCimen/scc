# SCC - Sandboxed Claude CLI

Run Claude Code in Docker sandboxes with organization-managed team profiles, marketplace integration, and git worktree support.

## Why this exists

Our teams needed a way to use Claude Code that was:
- **Isolated**: AI runs in containers, not directly on developer machines
- **Standardized**: Teams share configurations from a central organization config
- **Safe**: Protected branches stay protected, even when AI suggests changes
- **Pluggable**: Organization-specific Claude plugins via marketplace integration

## Prerequisites

- Python 3.10+
- Docker Desktop 4.50+ (for sandbox support)
- Git 2.30+

Run `scc doctor` to verify your setup.

## Installation

```bash
pip install scc-cli
```

Or with pipx for isolation:

```bash
pipx install scc-cli
```

## Quick start

```bash
# First run triggers a setup wizard
scc setup

# Or start directly with a workspace
scc start ~/projects/api-service --team platform

# Check system health
scc doctor
```

This runs Claude Code in a Docker sandbox with your repo mounted. Organization plugins are automatically injected based on your team profile.

## Setup modes

### Organization mode (recommended)

Connect to your organization's config to get team profiles and plugin access:

```bash
scc setup

# Enter your organization config URL when prompted:
# > https://gitlab.example.org/devops/scc-config.json
```

### Standalone mode

Use SCC without an organization config:

```bash
scc setup --standalone
```

## Common workflows

### Starting a session

```bash
# Interactive mode - prompts for team and workspace
scc

# Direct mode with team profile
scc start ~/projects/my-repo --team platform

# Continue most recent session
scc start --continue

# Offline mode (cache only)
scc start ~/projects/my-repo --offline
```

### Parallel development with worktrees

```bash
# Create isolated workspace for a feature
scc worktree ~/projects/api-service feature-auth
# Creates: ~/projects/api-service-worktrees/feature-auth/
# Branch: claude/feature-auth

# Work on urgent fix in parallel
scc worktree ~/projects/api-service hotfix-123

# Create worktree and install dependencies
scc worktree ~/projects/api-service feature-x --install-deps

# List worktrees
scc worktrees ~/projects/api-service

# Clean up when done
scc cleanup ~/projects/api-service feature-auth
```

### Managing teams and sessions

```bash
# List team profiles from organization config
scc teams

# Force refresh from remote
scc teams --sync

# List recent sessions
scc sessions

# List running sandboxes
scc list
```

## Commands

| Command | Description |
|---------|-------------|
| `scc` | Interactive mode with wizard |
| `scc setup` | Configure organization connection |
| `scc start <path>` | Start Claude Code in a sandbox |
| `scc stop` | Stop running sandbox(es) |
| `scc doctor` | Check prerequisites and system health |
| `scc teams` | List team profiles from org config |
| `scc sessions` | List recent sessions |
| `scc list` | List running Docker sandboxes |
| `scc worktree <repo> <name>` | Create git worktree for parallel work |
| `scc worktrees <repo>` | List worktrees for a repository |
| `scc cleanup <repo> <name>` | Remove a worktree |
| `scc config` | View or edit configuration |
| `scc config set <key> <value>` | Set configuration value |

Run `scc <command> --help` for detailed options.

## Configuration

### User config (`~/.config/scc/config.json`)

```json
{
  "organization_source": {
    "url": "https://gitlab.example.org/devops/scc-config.json",
    "auth": "env:GITLAB_TOKEN"
  },
  "selected_profile": "platform",
  "hooks": {
    "enabled": true
  }
}
```

### Organization config (IT-managed)

```json
{
  "organization": {
    "name": "Example Organization",
    "id": "example-org"
  },
  "marketplaces": [
    {
      "name": "internal",
      "type": "gitlab",
      "host": "gitlab.example.org",
      "repo": "group/claude-marketplace",
      "auth": "env:GITLAB_TOKEN"
    }
  ],
  "profiles": {
    "platform": {
      "description": "Platform team (Python, FastAPI)",
      "plugin": "platform",
      "marketplace": "internal"
    }
  }
}
```

Edit user config with `scc config --edit`.

## Authentication

| Method | Syntax | Example |
|--------|--------|---------|
| Environment variable | `env:VAR` | `"auth": "env:GITLAB_TOKEN"` |
| Command | `command:CMD` | `"auth": "command:op read op://Dev/token"` |
| None (public) | `null` | `"auth": null` |

## File locations

```
~/.config/scc/           # User configuration
├── config.json          # Organization URL, selected team, preferences

~/.cache/scc/            # Regenerable cache
├── org_config.json      # Cached remote org config
└── cache_meta.json      # ETags, timestamps

<repo>/.git/hooks/       # Repo-local hooks (if enabled)
└── pre-push             # Blocks pushes to protected branches
```

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 2 | Invalid usage |
| 3 | Missing prerequisites |
| 4 | External tool failure |
| 5 | Internal error |

## WSL2 users

Run inside WSL2, not Windows. Keep projects in the Linux filesystem (`~/projects`) rather than `/mnt/c/...` for acceptable performance. The CLI warns when it detects slow paths.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Docker not reachable" | Start Docker Desktop |
| "Docker version too old" | Update to Docker Desktop 4.50+ |
| "Organization config fetch failed" | Check URL and authentication token |
| Slow file operations (WSL2) | Move project to `~/projects`, not `/mnt/c/` |
| Permission denied on Linux | Add user to docker group: `sudo usermod -aG docker $USER` |

Run `scc doctor` to diagnose most issues.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) - System design and data flow

## License

MIT License. See [LICENSE](LICENSE).
