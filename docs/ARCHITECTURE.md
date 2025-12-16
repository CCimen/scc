# Architecture

This document explains how the CLI works and why it was designed this way.

## Overview

The CLI is a thin orchestration layer. It does not communicate with Claude's API directly. Instead, it prepares the environment and hands off to Docker, which runs the official Claude Code CLI inside a sandbox.

```
User runs: scc start ~/projects/api-service

    CLI (Python)
        |
        v
    1. Load team profile
    2. Check git branch safety
    3. Generate container name
    4. Build docker command
        |
        v
    os.execvp() --> Docker takes over
        |
        v
    Docker Sandbox
    +---------------------------+
    |  Claude Code (official)   |
    |  - workspace mounted      |
    |  - team config applied    |
    |  - connects to Claude API |
    +---------------------------+
```

After `os.execvp()`, the CLI process is replaced by Docker. This means zero overhead once the container starts.

## Security model

The "sandbox" provides process isolation, not security guarantees against a malicious AI.

**What's isolated:**
- Claude Code runs in a Docker container, not on the host
- Only the workspace directory is mounted (read/write)
- Container has network access (required for Claude API)

**What's not isolated:**
- The mounted workspace is fully accessible to Claude Code
- Environment variables passed to the container
- Network traffic is not restricted

**Branch protection:**
- The CLI checks if you're on a protected branch (main, master, develop) before starting
- If detected, it prompts to create a `claude/*` branch
- This is a preflight check, not enforcement—git hooks provide the actual block

**Credentials:**
- Claude API credentials come from the official Claude Code configuration
- The CLI does not handle or store API keys

## Key design decisions

### Container re-use over ephemeral containers

Each workspace+branch combination gets a deterministic container name: `scc-<workspace_hash>-<branch_hash>`. When you run `scc start` on the same workspace, it resumes the existing container rather than creating a new one.

Why: Claude Code maintains conversation context inside the container. Creating fresh containers loses this context. Resuming an existing container takes ~500ms vs ~3-5s for a new one.

Trade-off: Containers accumulate. Users need to periodically clean up with `docker container prune` or use `scc start --fresh`.

**Container labels:** Each container is tagged with:
- `scc.workspace`: absolute path to workspace
- `scc.branch`: git branch name
- `scc.team`: team profile used
- `scc.created`: ISO timestamp

These labels enable `scc list` to find and display containers, and allow targeted cleanup: `docker container prune --filter "label=scc.workspace"`.

### Worktrees for isolation, not branches

We use `git worktree` to create separate working directories rather than asking developers to switch branches. Each worktree gets its own container.

Why: Developers often need to context-switch (urgent bug while working on a feature). Worktrees let you have multiple Claude Code sessions running in parallel, each with its own state.

### Typed exceptions with user-facing messages

All errors inherit from `SCCError` and carry:
- `user_message`: Plain language explanation
- `suggested_action`: One concrete next step
- `exit_code`: For scripting (3=prerequisites, 4=external tool, 5=internal)

Why: Generic Python exceptions produce confusing output for non-developers. The error handler catches these and renders them as formatted panels.

### First-run detection over mandatory setup

The CLI checks `~/.config/sundsvalls-claude/config.json` for `setup_completed: true`. If missing, it runs a minimal wizard. No separate install step required.

Why: Reduces friction. Developers can `pip install` and immediately run `scc` without reading documentation.

## Module structure

```
src/sundsvalls_claude/
    cli.py          Entry point. Typer commands and error handling.
    config.py       Load/save configuration. Merge user config with defaults.
    docker.py       Build docker commands. Container existence checks.
    git.py          Branch safety. Worktree creation and cleanup.
    sessions.py     Track recent sessions. Link sessions to containers.
    teams.py        Load team profiles. GitHub sync.
    errors.py       Exception classes with exit codes.
    doctor.py       Prerequisite checks (git version, docker version, etc).
    platform.py     Detect macOS/Linux/WSL2. Path normalization.
    setup.py        First-run wizard.
    ui.py           Rich panels, tables, error rendering.
```

## Data flow

### Starting a session

1. `cli.py` receives the command
2. `config.py` loads user config, merges with defaults
3. `teams.py` loads team profile (local or GitHub)
4. `git.py` checks current branch, offers to create `claude/*` branch if needed
5. `docker.py` generates container name, checks if it exists
6. `sessions.py` records the session with container reference (before exec)
7. If exists: `os.execvp("docker", ["start", "-ai", name])` (resume)
8. If not: `os.execvp("docker", ["sandbox", "run", ...])` with workspace mount

Note: Session is recorded before `execvp()` because the CLI process is replaced by Docker. Nothing runs after exec.

### Error handling

1. Operation raises `SCCError` subclass (e.g., `PrerequisiteError`)
2. `@handle_errors` decorator in `cli.py` catches it
3. `ui.render_error()` formats the message as a panel
4. CLI exits with the error's exit code

## File locations

```
~/.config/sundsvalls-claude/
    config.json         User configuration
    sessions.json       Recent sessions with container links

~/projects/
    my-repo/            Main repository
    my-repo-worktrees/  Worktrees for my-repo
        feature-a/
        hotfix-123/
```

## Configuration priority

From highest to lowest:

1. Project local: `.claude/settings.local.json` (not committed)
2. Project shared: `.claude/settings.json` (committed)
3. Team profile: from `~/.config/sundsvalls-claude/` or GitHub
4. Base profile: organization defaults
5. Claude Code defaults

## Performance characteristics

| Operation | Time | Notes |
|-----------|------|-------|
| Config load | ~5ms | Single JSON read |
| Docker check | ~500ms | Subprocess to docker |
| Container resume | ~500ms | `docker start -ai` |
| Container create | 3-5s | Full `docker sandbox run` |
| Worktree create | 500ms-5min | Depends on deps installation |

Container re-use makes the typical case (resume) 10x faster than always creating fresh containers.

## Known limitations

- **WSL2 path performance**: Workspaces on `/mnt/c/...` are slow. The CLI warns but cannot fix this.
- **Container accumulation**: Old containers are not automatically cleaned up.
- **Single container per workspace+branch**: Cannot run multiple sessions on the same branch simultaneously.
