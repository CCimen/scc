# Architecture

This document explains how the CLI works and why it was designed this way.

## Overview

SCC is a thin orchestration layer that fetches organization configuration from a remote URL, resolves team profiles to marketplace plugins, and launches Claude Code in a Docker sandbox with the appropriate settings injected.

```
┌────────────────────────────────────────────────────────────────────────────┐
│  SCC – Sandboxed Claude CLI                                                │
│  • Fetches remote org config (any HTTPS URL)                               │
│  • Caches locally with TTL + ETag                                          │
│  • Validates schema, checks version compatibility                          │
│  • Manages git worktrees for parallel development                          │
│  • Enforces branch safety (opt-in repo-local hooks + runtime checks)       │
│  • Launches Docker sandbox with injected settings                          │
│  • Knows NOTHING about any specific organization                           │
│  • Does NOT download marketplace/plugin content                            │
└────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ HTTPS fetch (with ETag caching)
                                    ▼
┌────────────────────────────────────────────────────────────────────────────┐
│  Remote Organization Config (IT-managed)                                   │
│  • GitLab raw, GitHub raw, S3, any HTTPS endpoint                          │
│  • JSON file with: org identity, team profiles, marketplace refs           │
│  • Auth: env:VAR_NAME, command:CMD, or null (public)                       │
└────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ SCC passes REFERENCES ONLY to Claude Code
                                    ▼
┌────────────────────────────────────────────────────────────────────────────┐
│  Docker Sandbox with Claude Code                                           │
│  • Receives: extraKnownMarketplaces + enabledPlugins                       │
│  • Claude Code handles: fetching, installing, caching plugins              │
│  • SCC is completely hands-off after injection                             │
└────────────────────────────────────────────────────────────────────────────┘
```

## Security model

The "sandbox" provides process isolation, not security guarantees against a malicious AI.

**What's isolated:**
- Claude Code runs in a Docker container, not on the host
- Only the workspace directory is mounted (read/write)
- Container has network access (required for Claude API)

**What's not isolated:**
- The mounted workspace is fully accessible to Claude Code
- Environment variables passed to the container (including tokens)
- Network traffic is not restricted

**Branch protection:**
- The CLI checks if you're on a protected branch (main, master, develop) before starting
- If detected, it prompts to create a `claude/*` branch or worktree
- Repo-local pre-push hooks can block pushes to protected branches (opt-in)

**Credentials:**
- Organization config auth tokens resolved from env vars or commands
- Marketplace tokens injected into Docker env for Claude Code to use
- No tokens stored on disk or printed in logs

## Key design decisions

### Remote organization config

SCC does NOT hardcode organization-specific information. Instead:

1. User provides an HTTPS URL to their organization's config during `scc setup`
2. SCC fetches this JSON file with ETag caching (24h TTL by default)
3. The org config defines team profiles and marketplace references
4. SCC resolves `profile → plugin + marketplace` and injects into Docker

**Why**: Organizations can update their configs without requiring CLI updates. IT teams manage configs centrally.

### Module separation

| Module | Responsibility | Does NOT Do |
|--------|---------------|-------------|
| `profiles.py` | Profile resolution, marketplace URL logic | HTTP calls, file I/O |
| `remote.py` | HTTP fetch, auth, caching | Business logic, profile resolution |
| `claude_adapter.py` | Claude Code format knowledge | HTTP, profiles, caching |
| `validate.py` | Schema validation, version checks | HTTP, file I/O |
| `config.py` | Local config management | Remote fetching |
| `docker.py` | Docker sandbox execution | URL building, profiles |

**Why**: Each module has a single responsibility. `claude_adapter.py` isolates ALL Claude Code format knowledge, so if Claude changes their settings format, only one file needs updating.

### Container re-use over ephemeral containers

Each workspace+branch combination gets a deterministic container name: `scc-<workspace_hash>-<branch_hash>`. When you run `scc start` on the same workspace, it resumes the existing container rather than creating a new one.

**Why**: Claude Code maintains conversation context inside the container. Creating fresh containers loses this context. Resuming an existing container takes ~500ms vs ~3-5s for a new one.

**Trade-off**: Containers accumulate. Users need to periodically clean up with `docker container prune` or use `scc start --fresh`.

### Worktrees for isolation, not branches

We use `git worktree` to create separate working directories rather than asking developers to switch branches. Each worktree gets its own container.

**Why**: Developers often need to context-switch (urgent bug while working on a feature). Worktrees let you have multiple Claude Code sessions running in parallel, each with its own state.

### Typed exceptions with user-facing messages

All errors inherit from `SCCError` and carry:
- `user_message`: Plain language explanation
- `suggested_action`: One concrete next step
- `exit_code`: For scripting (3=prerequisites, 4=external tool, 5=internal)

**Why**: Generic Python exceptions produce confusing output for non-developers. The error handler catches these and renders them as formatted panels.

### XDG Base Directory compliance

Configuration is stored in XDG-compliant locations:
- `~/.config/scc/` - User configuration (backup-worthy)
- `~/.cache/scc/` - Regenerable cache (safe to delete)

**Why**: Follows standard conventions, allows easy backup/migration, cache can be safely deleted.

## Module structure

```
src/scc_cli/
    cli.py              Entry point. Typer commands and error handling.
    config.py           Load/save local configuration. XDG paths.
    profiles.py         Profile resolution, marketplace URL logic.
    remote.py           HTTP fetch, auth resolution, ETag caching.
    validate.py         Schema validation against bundled JSON schema.
    claude_adapter.py   Claude Code settings format (isolated).
    docker.py           Build docker commands. Credential injection.
    git.py              Branch safety. Worktree creation. Repo-local hooks.
    deps.py             Dependency detection and installation.
    sessions.py         Track recent sessions. Link sessions to containers.
    doctor.py           Prerequisite checks and health diagnostics.
    setup.py            Setup wizard for organization connection.
    errors.py           Exception classes with exit codes.
    platform.py         Detect macOS/Linux/WSL2. Path normalization.
    ui.py               Rich panels, tables, error rendering.
    schemas/
        org-v1.schema.json   Bundled schema for offline validation.
```

## Data flow

### Setup flow

```
scc setup
    │
    ├─ 1. Prompt for org config URL (or --standalone)
    ├─ 2. remote.py: Fetch org config with auth handling
    ├─ 3. validate.py: Validate against bundled schema
    ├─ 4. profiles.py: Extract available profiles
    ├─ 5. ui.py: Prompt for profile selection
    ├─ 6. config.py: Save user config
    └─ 7. git.py: Optionally install repo-local hooks
```

### Start flow

```
scc start ~/projects/my-repo --team platform
    │
    ├─ 1. config.py: Load user config
    ├─ 2. remote.py: Load org config (cache or refresh)
    ├─ 3. validate.py: Check schema/version compatibility
    ├─ 4. profiles.py: Resolve profile → plugin + marketplace
    ├─ 5. git.py: Check branch safety, offer alternatives
    ├─ 6. claude_adapter.py: Build Claude settings payload
    ├─ 7. docker.py: Inject credentials, build docker command
    ├─ 8. sessions.py: Record session before exec
    └─ 9. os.execvp() → Docker takes over
```

### Error handling

1. Operation raises `SCCError` subclass (e.g., `PrerequisiteError`)
2. `@handle_errors` decorator in `cli.py` catches it
3. `ui.render_error()` formats the message as a panel
4. CLI exits with the error's exit code

## File locations

```
~/.config/scc/
    config.json         User configuration (org URL, selected profile)

~/.cache/scc/
    org_config.json     Cached remote org config
    cache_meta.json     ETags, timestamps, fingerprints

~/projects/
    my-repo/            Main repository
    my-repo-worktrees/  Worktrees for my-repo
        feature-a/
        hotfix-123/

<repo>/.git/hooks/
    pre-push            SCC-managed hook (if hooks.enabled=true)
```

## Configuration priority

From highest to lowest:

1. CLI flags: `--team`, `--offline`, etc.
2. User config: `~/.config/scc/config.json`
3. Organization config: Remote-fetched, cached locally
4. Built-in defaults

## Authentication flow

```
User config:                  Organization config:
"auth": "env:GITLAB_TOKEN"    "auth": "env:ORG_TOKEN"
           │                             │
           ▼                             ▼
    resolve_auth()                resolve_auth()
           │                             │
           ▼                             ▼
    Token for org fetch          Token for marketplace
           │                             │
           ▼                             ▼
    Fetch org config             Inject into Docker env
```

Auth methods:
- `env:VAR_NAME` - Read from environment variable
- `command:CMD` - Execute command, use stdout as token
- `null` - No authentication (public URLs)

## Performance characteristics

| Operation | Time | Notes |
|-----------|------|-------|
| Config load | ~5ms | Single JSON read |
| Cache check | ~5ms | Read + TTL comparison |
| Org config fetch | 100-500ms | HTTP with auth |
| Schema validation | ~10ms | Against bundled schema |
| Docker check | ~500ms | Subprocess to docker |
| Container resume | ~500ms | `docker start -ai` |
| Container create | 3-5s | Full `docker sandbox run` |
| Worktree create | 500ms-5min | Depends on deps installation |

Container re-use makes the typical case (resume) 10x faster than always creating fresh containers.

## Known limitations

- **WSL2 path performance**: Workspaces on `/mnt/c/...` are slow. The CLI warns but cannot fix this.
- **Container accumulation**: Old containers are not automatically cleaned up.
- **Single container per workspace+branch**: Cannot run multiple sessions on the same branch simultaneously.
- **Network dependency**: Org config fetch requires network (use `--offline` for cache-only).

## What SCC does NOT do

SCC is intentionally minimal. It does NOT:

- Download or cache plugin content (Claude Code does this)
- Verify plugin integrity (no checksum verification)
- Maintain a local marketplace mirror
- Communicate with Claude's API directly
- Handle Claude Code authentication

SCC only:
- Fetches and caches organization config
- Resolves profiles to marketplace references
- Injects settings into Docker environment
- Manages git worktrees and branch safety
