# SCC - Sandboxed Claude CLI

Run Claude Code in Docker sandboxes with organization-managed team profiles, marketplace integration, and git worktree support.

SCC isolates AI execution in containers, enforces branch safety, and lets organizations distribute Claude plugins through a central configuration. Developers get standardized setups without manual configuration.

## Installation

```bash
pip install scc-cli
```

Or with pipx:

```bash
pipx install scc-cli
```

Requires Python 3.10+, Docker Desktop 4.50+, and Git 2.30+.

## Quick Start

```bash
# Run setup wizard
scc setup

# Start Claude Code in a sandbox
scc start ~/projects/api-service --team platform

# Check system health
scc doctor
```

## Usage

### Starting sessions

```bash
# Interactive mode
scc

# With team profile
scc start ~/projects/my-repo --team platform

# Continue most recent session
scc start --continue

# Offline mode (cache only)
scc start ~/projects/my-repo --offline
```

### Parallel development with worktrees

```bash
# Create isolated workspace
scc worktree ~/projects/api-service feature-auth
# Creates: ~/projects/api-service-worktrees/feature-auth/
# Branch: claude/feature-auth

# With dependency installation
scc worktree ~/projects/api-service feature-x --install-deps

# List worktrees
scc worktrees ~/projects/api-service

# Clean up
scc cleanup ~/projects/api-service feature-auth
```

### Managing configuration

```bash
# List team profiles
scc teams

# Refresh from remote
scc teams --sync

# Check for CLI and config updates
scc update

# Force update check
scc update --force

# List recent sessions
scc sessions
```

## Commands

| Command | Description |
|---------|-------------|
| `scc` | Interactive mode |
| `scc setup` | Configure organization connection |
| `scc start <path>` | Start Claude Code in sandbox |
| `scc stop` | Stop running sandbox(es) |
| `scc doctor` | Check prerequisites |
| `scc update` | Check for CLI and config updates |
| `scc teams` | List team profiles |
| `scc sessions` | List recent sessions |
| `scc list` | List running containers |
| `scc worktree <repo> <name>` | Create git worktree |
| `scc worktrees <repo>` | List worktrees |
| `scc cleanup <repo> <name>` | Remove worktree |
| `scc config` | View or edit configuration |

Run `scc <command> --help` for options.

## Configuration

### Setup modes

Organization mode connects to a central config:

```bash
scc setup
# Enter URL when prompted: https://gitlab.example.org/devops/scc-config.json
```

Standalone mode runs without organization config:

```bash
scc setup --standalone
```

### User config

Located at `~/.config/scc/config.json`:

```json
{
  "organization_source": {
    "url": "https://gitlab.example.org/devops/scc-config.json",
    "auth": "env:GITLAB_TOKEN"
  },
  "selected_profile": "platform",
  "hooks": { "enabled": true }
}
```

Edit with `scc config --edit`.

### Authentication methods

| Method | Syntax |
|--------|--------|
| Environment variable | `"auth": "env:GITLAB_TOKEN"` |
| Command | `"auth": "command:op read op://Dev/token"` |
| None (public) | `"auth": null` |

### File locations

```
~/.config/scc/           # Configuration
├── config.json          # Org URL, team, preferences

~/.cache/scc/            # Cache (safe to delete)
├── org_config.json      # Remote config cache
└── cache_meta.json      # ETags, timestamps
```

## Troubleshooting

Run `scc doctor` to diagnose issues.

| Problem | Solution |
|---------|----------|
| Docker not reachable | Start Docker Desktop |
| Organization config fetch failed | Check URL and token |
| Slow file operations (WSL2) | Move project to `~/projects`, not `/mnt/c/` |
| Permission denied (Linux) | `sudo usermod -aG docker $USER` |

### WSL2

Run inside WSL2, not Windows. Keep projects in the Linux filesystem for acceptable performance.

## Development

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Run linter
uv run ruff check --fix
```

See [CLAUDE.md](CLAUDE.md) for development methodology.

## License

MIT
