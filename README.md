# Sundsvalls Claude CLI

A CLI for running Claude Code in Docker sandboxes with team-based configuration and git worktree support. Built for Sundsvalls kommun to standardize AI-assisted development across teams.

## Why this exists

Our teams needed a way to use Claude Code that was:
- **Isolated**: AI runs in containers, not directly on developer machines
- **Standardized**: Teams share configurations, not tribal knowledge
- **Safe**: Protected branches stay protected, even when AI suggests changes

## Prerequisites

- Python 3.10+
- Docker Desktop 4.50+ (for sandbox support)
- Git 2.30+

Run `scc doctor` to verify your setup.

## Installation

```bash
pip install sundsvalls-claude
```

Or with pipx for isolation:

```bash
pipx install sundsvalls-claude
```

## Quick start

```bash
# First run triggers a setup wizard
scc

# Or start directly with a workspace
scc start ~/projects/api-service --team java-wso2

# Check system health
scc doctor
```

This starts (or resumes) a Docker container with your repo mounted. Claude Code runs inside the container and connects to the Claude API.

## Common workflows

### Starting a session

```bash
# Interactive mode - prompts for team and workspace
scc

# Direct mode with team profile
scc start ~/projects/my-repo --team python-fastapi

# Resume previous session (containers persist)
scc start ~/projects/my-repo

# Force fresh container
scc start ~/projects/my-repo --fresh
```

### Parallel development with worktrees

```bash
# Create isolated workspace for a feature
scc worktree ~/projects/api-service feature-auth
# Creates: ~/projects/api-service-worktrees/feature-auth/
# Branch: claude/feature-auth

# Work on urgent fix in parallel
scc worktree ~/projects/api-service hotfix-123

# List worktrees
scc worktrees ~/projects/api-service

# Clean up when done
scc cleanup ~/projects/api-service feature-auth
```

### Managing teams and sessions

```bash
# List team profiles
scc teams

# Show team details
scc teams java-wso2

# Sync profiles from GitHub
scc teams --sync

# List recent sessions
scc sessions

# List running containers
scc list
```

## Commands

| Command | Description |
|---------|-------------|
| `scc` | Interactive mode with wizard |
| `scc start <path>` | Start or resume Claude Code in workspace |
| `scc doctor` | Check prerequisites and system health |
| `scc teams` | List, view, or sync team profiles |
| `scc sessions` | List recent sessions |
| `scc list` | List managed Docker containers |
| `scc worktree <repo> <name>` | Create git worktree for parallel work |
| `scc worktrees <repo>` | List worktrees for a repository |
| `scc cleanup <repo> <name>` | Remove a worktree |
| `scc config` | View or edit configuration |
| `scc setup` | Run setup wizard |

Run `scc <command> --help` for detailed options.

## Configuration

Config lives in `~/.config/sundsvalls-claude/config.json`:

```json
{
  "workspace_base": "~/projects",
  "profiles": {
    "java-wso2": {
      "description": "Java/Spring Boot/WSO2",
      "tools": ["java", "maven"]
    }
  }
}
```

Edit with `scc config --edit`.

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
| Slow file operations (WSL2) | Move project to `~/projects`, not `/mnt/c/` |
| Stale container state | Use `scc start --fresh` to force new container |
| Permission denied on Linux | Add user to docker group: `sudo usermod -aG docker $USER` |

Run `scc doctor` to diagnose most issues.

## Cleanup

Containers persist for session continuity. To clean up:

```bash
# Remove all stopped scc containers
docker container prune --filter "label=scc.workspace"

# Or remove a specific container
docker rm scc-<workspace>-<branch>

# List scc containers to find names
scc list
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) - System design and data flow
- [Contributing](CONTRIBUTING.md) - Development setup and PR process

## License

MIT License. See [LICENSE](LICENSE).
