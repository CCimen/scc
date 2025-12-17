# Architecture

SCC runs Claude Code in Docker containers with mounted workspaces. It pulls org config from a URL, expands team profiles into plugin sets, and injects settings into the sandbox.

## Overview

```mermaid
graph LR
    Dev[Developer] --> CLI[SCC CLI]
    CLI -->|fetch| Config[Remote Config]
    CLI -->|launch| Sandbox[Docker Sandbox]
    Sandbox --> Claude[Claude Code]
    Claude -->|calls| API[Claude API]
    Claude <-->|read/write| Workspace[Workspace]
```

SCC acts as orchestration layer only. It does not download plugins, communicate with Claude's API, or run any AI logic. Claude Code inside the container handles all of that.

## Scope

What SCC does:
- Fetches and caches organization config from any HTTPS URL
- Resolves team profiles to marketplace plugin references
- Manages git worktrees for parallel development
- Enforces branch safety via repo-local hooks
- Launches Docker sandbox with injected credentials
- Checks for CLI updates from PyPI
- Notifies when org config has changed remotely

What SCC does not do:
- Download or cache plugin content
- Verify plugin integrity or signatures
- Communicate with Claude's API
- Restrict container network traffic

## Security Model

Docker provides process isolation, not containment of a malicious model.

```mermaid
graph TB
    subgraph Host[Host Machine]
        CLI[SCC CLI]
        Config[Local Config]
        Creds[Credentials]
    end

    subgraph Container[Docker Sandbox]
        Claude[Claude Code]
        Plugins[Plugins]
    end

    Workspace[Workspace Dir]
    Network[Network]

    CLI -->|launch| Container
    CLI -->|inject env vars| Container
    CLI -->|fetch config| Network
    Container <-->|mount| Workspace
    Container -->|API calls| Network
```

Trust boundaries:

| Boundary | Isolated | Shared |
|----------|----------|--------|
| Filesystem | Host system | Mounted workspace (read/write) |
| Process | Host processes | Container processes |
| Network | None | Full access (required for Claude API) |
| Environment | Host env vars | Explicitly passed tokens |

Credential flow:
- Tokens resolved from `env:VAR` or `command:CMD` syntax
- Injected into container via Docker environment variables
- Never written to disk or printed in logs

## Module Design

```mermaid
graph TD
    CLI[cli.py] --> Config[config.py]
    CLI --> Remote[remote.py]
    CLI --> Docker[docker.py]
    CLI --> Git[git.py]
    CLI --> Update[update.py]
    CLI --> Setup[setup.py]
    CLI --> Doctor[doctor.py]

    Remote --> Validate[validate.py]

    Docker --> Adapter[claude_adapter.py]
    Docker --> Sessions[sessions.py]
    Docker --> Deps[deps.py]

    Adapter --> Profiles[profiles.py]
```

Module responsibilities:

| Module | Does | Does Not |
|--------|------|----------|
| `profiles.py` | Profile resolution, marketplace URLs | HTTP, file I/O |
| `remote.py` | HTTP fetch, auth, ETag caching | Business logic |
| `claude_adapter.py` | Claude Code format knowledge | HTTP, profiles |
| `validate.py` | Schema validation | HTTP, file I/O |
| `config.py` | Local config, XDG paths | Remote fetching |
| `docker.py` | Container lifecycle, credential injection | URL building |
| `update.py` | Version checking, throttling, notifications | Container operations |

The `claude_adapter.py` module isolates all Claude Code format knowledge. When Claude changes their settings format, only this file needs updating.

## Update System

SCC checks for updates to both the CLI package and organization config.

### Throttling

Update checks are throttled to avoid excessive network requests:

| Check Type | Interval | Rationale |
|------------|----------|-----------|
| CLI version (PyPI) | 24 hours | Package releases are infrequent |
| Org config | 1 hour | Config changes need faster propagation |

Throttle state is stored in `~/.cache/scc/update_check_meta.json`:

```json
{
  "last_cli_check": "2025-12-17T10:00:00Z",
  "last_org_config_check": "2025-12-17T14:30:00Z"
}
```

### CLI Updates

The CLI fetches version info from PyPI's JSON API:

```
GET https://pypi.org/pypi/scc-cli/json
→ Extract info.version
→ Compare with installed version
→ Detect install method (pip, pipx, uv)
→ Generate appropriate upgrade command
```

### Org Config Updates

Org config updates use ETag-based conditional fetching:

```
GET https://example.org/config.json
If-None-Match: "abc123"

→ 304 Not Modified: Use cache, no action needed
→ 200 OK: Config updated, refresh cache
→ 401/403: Auth failed, warn user
→ Network error: Use stale cache if available
```

### Notification Behavior

During `scc start`, non-intrusive notifications appear for:
- CLI updates available (shows upgrade command)
- Org config updated from remote
- Auth failures when stale cache exists

The `scc update` command forces immediate checks and shows detailed status.

## Lifecycle Flows

### Setup

```
User: scc setup
CLI: Prompt for org URL
User: https://example.org/config.json
CLI: GET config (with auth if needed)
CLI: Validate against schema
CLI: Prompt for team profile
User: platform
CLI: Save to ~/.config/scc/
```

### Start Session

```
User: scc start ~/repo --team platform
CLI: Check org config TTL
     └─ Cache valid? Use cache
     └─ Cache expired? GET with If-None-Match
        └─ 304? Use cache
        └─ 200? Update cache
CLI: Resolve profile → plugin + marketplace
CLI: Check branch safety
CLI: docker sandbox run (workspace mount, env vars)
```

## Configuration Precedence

From highest to lowest priority:

1. CLI flags (`--team`, `--offline`)
2. User config (`~/.config/scc/config.json`)
3. Organization config (remote-fetched, cached)
4. Built-in defaults

## File Locations

```
~/.config/scc/
    config.json              # Org URL, selected profile, preferences

~/.cache/scc/
    org_config.json          # Cached remote config
    cache_meta.json          # ETags, timestamps
    update_check_meta.json   # Update check throttling

~/projects/
    my-repo/                 # Main repository
    my-repo-worktrees/       # Worktrees created by SCC
        feature-a/
        hotfix-123/

<repo>/.git/hooks/
    pre-push                 # SCC-managed hook (opt-in)
```

## Performance

| Operation | Time | Notes |
|-----------|------|-------|
| Container resume | ~500ms | Typical with re-use |
| Container create | 3-5s | Cold start |
| Config fetch | 100-500ms | HTTP with auth |
| Cache check | ~5ms | Local TTL comparison |
| Update check | 200-800ms | PyPI + org config (when not throttled) |
| Worktree create | 500ms-5min | Depends on `--install-deps` |

Container re-use makes resume 10x faster than fresh containers. Each workspace+branch combination gets a deterministic container name for automatic re-use.

## Design Decisions

### Why remote config?

Organizations update their configs without requiring CLI updates. IT teams manage profiles centrally. One URL change propagates to all developers.

### Why throttled update checks?

Checking PyPI and remote config on every command would add latency. Throttling (24h for CLI, 1h for org config) balances freshness with responsiveness.

### Why worktrees over branches?

Developers context-switch frequently. Worktrees allow multiple Claude Code sessions running in parallel, each with its own container and conversation state.

### Why container re-use?

Claude Code maintains conversation context inside the container. Fresh containers lose this context. Trade-off: containers accumulate and need periodic cleanup with `docker container prune`.

### Why XDG paths?

Standard conventions allow easy backup (`~/.config/scc/`) while keeping regenerable cache separate (`~/.cache/scc/`). Cache deletion is always safe.

### Why typed exceptions?

All errors inherit from `SCCError` with:
- `user_message`: Plain language explanation
- `suggested_action`: Concrete next step
- `exit_code`: For scripting (3=prerequisites, 4=external tool, 5=internal)

## Limitations

- WSL2 performance: Workspaces on `/mnt/c/...` are slow. CLI warns but cannot fix this.
- Container accumulation: Old containers not auto-cleaned. Run `docker container prune` periodically.
- Single session per branch: Cannot run multiple sessions on same workspace+branch simultaneously.
- Network required: Org config fetch needs network. Use `--offline` for cache-only mode.
