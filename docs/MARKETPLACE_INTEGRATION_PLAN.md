# SCC Marketplace Integration Plan (vFinal-Complete)

**Status**: Ready for Implementation
**Validated by**: GPT-5.2, Gemini-3-Pro-Preview consensus
**Last Updated**: 2025-12-25
**Revision**: 5 (schema fixes + source-agnostic design + manual updates + Phase 1 scope)

---

## Executive Summary

This plan implements marketplace and plugin management for SCC organization configs, enabling teams to define plugin sources and compute effective plugin sets that render to Claude Code's `settings.local.json` format.

### Key Design Principles
1. **Team Autonomy**: Teams define their own bootstrap plugins
2. **Light Governance**: Org admins can block specific plugins with escape hatch
3. **Non-Destructive**: Preserve user additions when switching teams
4. **Phase 1 Scope**: Only `settings.local.json`, never global settings
5. **Implicit Built-ins**: `claude-plugins-official` is built-in, never written
6. **Materialization Strategy**: SCC fetches all sources → emits as `directory` to Claude Code
7. **Project-Local Paths**: Materialized caches live inside project for sandbox visibility
8. **Lazy Materialization**: Only materialize marketplaces when actually needed
9. **Fail-Fast Validation**: Hard errors on invalid refs, warnings only for advisory info

### Critical Architecture Decision: Materialization

**Problem**: Claude Code's `extraKnownMarketplaces` only supports `github`, `git`, and `directory` sources (per official docs). It does NOT support `url`, `npm`, or `file` in `extraKnownMarketplaces`.

**Solution**: SCC materializes ALL marketplace types to **project-local** directories, then emits them as `directory` sources:

```
┌─────────────────────────────────────────────────────────────────┐
│  SCC Org Config (supports 6 source types)                       │
│  ├── github: sundsvall-kommun/claude-plugins                    │
│  ├── git: https://gitlab.internal/plugins.git                   │
│  ├── url: https://plugins.sundsvall.se/marketplace.json         │
│  ├── npm: @sundsvall/claude-plugins                             │
│  ├── file: /shared/plugins/marketplace.json                     │
│  └── directory: /opt/claude-plugins                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼  SCC fetches & caches (LAZY - only on `start`)
┌─────────────────────────────────────────────────────────────────┐
│  <project>/.claude/.scc-marketplaces/                           │
│  ├── internal-plugins/      (materialized from url)             │
│  │   └── .claude-plugin/                                        │
│  │       └── marketplace.json                                   │
│  ├── team-shared/           (materialized from github)          │
│  │   └── .claude-plugin/                                        │
│  │       └── marketplace.json                                   │
│  └── .manifest.json         (tracks source → cache mapping)     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼  SCC emits RELATIVE paths (sandbox-safe)
┌─────────────────────────────────────────────────────────────────┐
│  .claude/settings.local.json                                    │
│  {                                                              │
│    "extraKnownMarketplaces": {                                  │
│      "internal-plugins": {                                      │
│        "source": {                                              │
│          "source": "directory",                                 │
│          "path": ".claude/.scc-marketplaces/internal-plugins"   │
│        }                                                        │
│      }                                                          │
│    }                                                            │
│  }                                                              │
└─────────────────────────────────────────────────────────────────┘
```

**Benefits**:
- Works with Claude Code's documented `extraKnownMarketplaces` limitations
- **Sandbox-safe**: Project-local paths are visible inside Docker sandbox
- No credentials needed in sandbox (SCC fetches on host before launch)
- Deterministic: pinned versions cached locally
- All 6 source types supported in org config
- Portable: works across machines (relative paths)

### Critical Architecture Decision: Sandbox Path Visibility

**Problem**: SCC runs Claude Code inside a Docker sandbox. If marketplace caches live in `~/.cache/scc/`, the sandbox can't see them unless explicitly mounted.

**Solution**: Materialize marketplaces into **project-local** directory:
- Location: `<project>/.claude/.scc-marketplaces/<name>/`
- Settings reference: **relative path** (e.g., `.claude/.scc-marketplaces/internal-plugins`)
- Sandbox automatically sees it (project is mounted at `/workspace`)

**Why NOT `~/.cache/scc/`**:
```
# This FAILS in sandbox (path not visible):
"path": "/Users/dev/.cache/scc/marketplaces/internal-plugins"

# This WORKS (project-relative, visible at /workspace/.claude/...):
"path": ".claude/.scc-marketplaces/internal-plugins"
```

**Docker Sandbox Context** (from Docker docs):
- `docker sandbox run claude` mounts current directory as workspace
- Volume mounts (`-v`) require explicit flags and recreating sandbox
- Project-local caches avoid needing custom volume mounts

---

## 1. Schema Structure

### 1.1 MarketplaceSource Definition (SCC Org Config)

SCC supports 6 source types internally. These get materialized to directories before emitting to Claude Code.

```json
{
  "MarketplaceSource": {
    "oneOf": [
      {
        "source": "github",
        "properties": {
          "repo": "string (required, format: 'owner/repo')",
          "ref": "string (optional, branch/tag/commit)",
          "path": "string (optional, subdirectory path)"
        }
      },
      {
        "source": "git",
        "properties": {
          "url": "string (required, git:// or https://...git)",
          "ref": "string (optional, branch/tag/commit)",
          "path": "string (optional, subdirectory)"
        }
      },
      {
        "source": "url",
        "properties": {
          "url": "string (required, https://)",
          "headers": {
            "type": "object",
            "additionalProperties": "string",
            "description": "HTTP headers for authentication"
          }
        }
      },
      {
        "source": "directory",
        "properties": {
          "path": "string (required, absolute path)"
        }
      },
      {
        "source": "file",
        "properties": {
          "path": "string (required, absolute path to marketplace.json)"
        }
      },
      {
        "source": "npm",
        "properties": {
          "package": "string (required)",
          "version": "string (optional)"
        }
      }
    ]
  }
}
```

> **⚠️ Vocabulary Note: Two Different "Source" Contexts**
>
> The word "source" has two distinct meanings in this system:
>
> | Context | Where Used | Values |
> |---------|------------|--------|
> | **Marketplace Source** | `extraKnownMarketplaces` in settings.local.json | `github`, `git`, `directory` only |
> | **Plugin Source** | `plugins[].source` in marketplace.json | Relative path string like `"./plugins/my-plugin"` |
>
> **SCC's 6 internal source types** (`github`, `git`, `url`, `directory`, `file`, `npm`) are for fetching marketplaces. After materialization, SCC emits only `directory` sources to Claude Code.
>
> **Plugin sources in marketplace.json** are paths within the marketplace, not external URLs. Keep them as relative paths (e.g., `"./plugins/api-tools"`) for simplest materialization.

### 1.2 Key Schema Corrections (from Claude Code docs)

| Field | Correct | Wrong |
|-------|---------|-------|
| URL auth headers | `headers` | ~~`httpHeaders`~~ |
| Directory path | `"source": "directory", "path": "..."` | ~~`"directory": "..."`~~ |
| GitHub repo | `"repo": "owner/repo"` | ~~`"owner": "x", "repo": "y"`~~ |

### 1.3 Example Marketplace Sources in Org Config

```json
{
  "marketplaces": {
    "internal-plugins": {
      "source": {
        "source": "url",
        "url": "https://plugins.sundsvall.se/marketplace.json",
        "headers": {
          "Authorization": "Bearer ${SUNDSVALL_PLUGIN_TOKEN}"
        }
      },
      "autoUpdate": true,
      "description": "Internal Sundsvall plugins"
    },
    "team-shared": {
      "source": {
        "source": "github",
        "repo": "sundsvall-kommun/claude-plugins",
        "ref": "v2.1.0",
        "path": "plugins"
      }
    },
    "local-dev": {
      "source": {
        "source": "directory",
        "path": "/opt/claude-plugins"
      }
    }
  }
}
```

### 1.4 Org Config Schema Extensions

```json
{
  "marketplaces": {
    "type": "object",
    "description": "Named marketplace sources (keys must NOT shadow implicit marketplaces)",
    "additionalProperties": {
      "type": "object",
      "properties": {
        "source": { "$ref": "#/definitions/MarketplaceSource" },
        "autoUpdate": { "type": "boolean" },
        "description": { "type": "string" }
      },
      "required": ["source"]
    }
  },

  "defaults": {
    "properties": {
      "enabled_plugins": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Base plugins enabled for all teams"
      },
      "allowed_plugins": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Patterns of plugins allowed (if set, only matching plugins can be enabled)"
      },
      "extra_marketplaces": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Marketplaces to expose without enabling plugins"
      }
    }
  },

  "profiles": {
    "additionalProperties": {
      "properties": {
        "additional_plugins": {
          "type": "array",
          "items": {"type": "string"},
          "description": "Plugins to add on top of defaults"
        },
        "disabled_plugins": {
          "type": "array",
          "items": {"type": "string"},
          "description": "Patterns to disable (name-only matches any marketplace)"
        },
        "extra_marketplaces": {
          "type": "array",
          "items": {"type": "string"},
          "description": "Team-specific marketplaces to expose"
        }
      }
    }
  },

  "security": {
    "properties": {
      "blocked_plugins": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Patterns to block (fnmatch wildcards)"
      },
      "block_implicit_marketplaces": {
        "type": "boolean",
        "default": false,
        "description": "Block non-explicitly-defined marketplaces"
      }
    }
  }
}
```

### 1.5 Source-Agnostic Design

**SCC is agnostic about where org configs and marketplaces are hosted.**

| Hosting Option | How It Works |
|----------------|--------------|
| Private GitLab (on-prem) | `git` source with internal URL |
| GitHub (public or private) | `github` source with `owner/repo` |
| Public GitLab | `git` source with gitlab.com URL |
| Any HTTPS endpoint | `url` source pointing to JSON/archive |
| Local filesystem | `directory` source for testing |

**SCC's responsibility:**
- Fetch from the configured source (with auth if needed)
- Materialize to project-local cache
- Write settings for Claude Code

**Organization's responsibility:**
- Choose where to host configs and marketplaces
- Set up access controls (tokens, SSO, etc.)
- Manage versioning and releases
- Define team structure and governance

**Example: Same org config, different hosting:**

```json
// Option A: Private GitLab
"marketplaces": {
  "backend": {
    "source": {
      "source": "git",
      "url": "https://gitlab.internal/ai/marketplaces.git",
      "ref": "v2025.01",
      "path": "marketplaces/backend"
    }
  }
}

// Option B: GitHub
"marketplaces": {
  "backend": {
    "source": {
      "source": "github",
      "repo": "company/claude-marketplaces",
      "ref": "v2025.01",
      "path": "marketplaces/backend"
    }
  }
}

// Option C: Direct URL
"marketplaces": {
  "backend": {
    "source": {
      "source": "url",
      "url": "https://plugins.company.com/backend-marketplace.zip"
    }
  }
}
```

All three work identically from SCC's perspective.

---

## 2. Marketplace Materialization

### 2.1 Project-Local Cache Directory Structure

**CRITICAL**: Caches live INSIDE the project for sandbox visibility.

```
<project>/
├── .claude/
│   ├── settings.local.json         # Claude Code reads this
│   ├── .scc-managed.json           # SCC tracking metadata
│   └── .scc-marketplaces/          # ← PROJECT-LOCAL materialized cache
│       ├── internal-plugins/       # Materialized from URL
│       │   └── .claude-plugin/     # ← REQUIRED: valid marketplace structure
│       │       ├── marketplace.json
│       │       └── plugins/
│       │           └── code-standards/
│       │               └── plugin.json
│       ├── team-shared/            # Materialized from GitHub
│       │   └── .claude-plugin/
│       │       └── marketplace.json
│       └── .manifest.json          # Tracks source → cache mapping
└── ...

~/.cache/scc/
├── org_config.json                 # Cached org config (NOT marketplaces)
└── cache_meta.json                 # ETags, timestamps
```

### 2.2 Valid Directory Marketplace Structure

**CRITICAL**: A `directory` marketplace MUST contain `.claude-plugin/marketplace.json`.
Claude Code expects this exact structure - a folder with "some JSON somewhere" won't work.

```
<marketplace-name>/
├── .claude-plugin/                  # ← Marketplace-level manifest
│   └── marketplace.json             # ← Required: defines available plugins
└── plugins/
    └── <plugin-name>/
        ├── .claude-plugin/          # ← Plugin-level manifest
        │   └── plugin.json          # ← Required: plugin definition
        ├── commands/                # ← At plugin root (NOT inside .claude-plugin/)
        ├── agents/                  # ← At plugin root
        ├── skills/                  # ← At plugin root
        ├── hooks/                   # ← At plugin root
        ├── CLAUDE.md                # ← Optional
        └── ...
```

**Key Rule** (from Claude Code docs):
> The `.claude-plugin/` directory contains ONLY the manifest file (`plugin.json`).
> All functional directories (`commands/`, `agents/`, `skills/`, `hooks/`) MUST be at the plugin root level, NOT inside `.claude-plugin/`.

**marketplace.json structure** (per Claude Code marketplace format):
```json
{
  "name": "internal-plugins",
  "owner": {
    "name": "Sundsvall IT"
  },
  "metadata": {
    "description": "Internal Sundsvall plugins"
  },
  "plugins": [
    {
      "name": "code-standards",
      "description": "Code standards enforcement",
      "source": "./plugins/code-standards"
    }
  ]
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `name` | ✅ | Marketplace identifier |
| `owner.name` | ✅ | Attribution for marketplace |
| `metadata.description` | ⚠️ | Recommended for discoverability |
| `plugins[].name` | ✅ | Plugin identifier |
| `plugins[].source` | ✅ | Relative path to plugin directory |

The materializer MUST create this exact structure, not just copy files.

### 2.3 Manifest Schema

Located at `<project>/.claude/.scc-marketplaces/.manifest.json`:

```json
{
  "version": 1,
  "project_path": "/path/to/project",
  "marketplaces": {
    "internal-plugins": {
      "source_type": "url",
      "source_url": "https://plugins.sundsvall.se/marketplace.json",
      "materialization_mode": "self_contained",
      "cached_at": "2025-12-25T10:30:00Z",
      "relative_path": ".claude/.scc-marketplaces/internal-plugins",
      "etag": "W/\"abc123\"",
      "plugins_included": ["code-standards", "api-tools"]
    },
    "team-shared": {
      "source_type": "github",
      "source_repo": "sundsvall-kommun/claude-plugins",
      "source_ref": "v2.1.0",
      "materialization_mode": "complete",
      "cached_at": "2025-12-25T10:30:00Z",
      "relative_path": ".claude/.scc-marketplaces/team-shared",
      "commit_sha": "abc123def456",
      "plugins_included": ["backend-tools", "frontend-tools"]
    }
  }
}
```

### 2.4 URL Marketplace Materialization Guarantees

**CRITICAL DISTINCTION**: "SCC fetches so no creds in sandbox" is only fully true for certain source types.

| Source Type | Materialization Guarantee | Creds at Install Time? |
|-------------|---------------------------|------------------------|
| `github` | **Complete** - entire repo cloned | ❌ No |
| `git` | **Complete** - entire repo cloned | ❌ No |
| `directory` | **Complete** - already local | ❌ No |
| `url` | **Best-effort** - see below | ⚠️ Maybe |
| `npm` | **Complete** - package downloaded | ❌ No |
| `file` | **Complete** - file copied | ❌ No |

**URL Marketplace Problem**:
A `url` marketplace's `marketplace.json` may reference plugins at **remote locations**:
```json
{
  "plugins": [
    {"name": "internal-tool", "source": "https://private.server/plugins/internal-tool.zip"}
  ]
}
```

If SCC only caches the metadata, Claude Code will need credentials at install time.

**Solution Options** (choose one per org):

1. **Self-Contained URL Bundles** (Recommended):
   - Constrain URL marketplaces to contain all plugin content inline or as relative paths
   - SCC materializes everything including plugin sources
   - Zero creds needed at Claude Code install time

2. **Best-Effort Metadata Caching**:
   - SCC caches `marketplace.json` only
   - Plugin sources fetched by Claude Code at install time
   - May require credentials in sandbox (less secure)

**Schema Addition for URL Sources**:
```json
{
  "marketplaces": {
    "internal-plugins": {
      "source": {
        "source": "url",
        "url": "https://plugins.sundsvall.se/bundle.zip",
        "headers": { "Authorization": "Bearer ${TOKEN}" }
      },
      "materialization": "self_contained"  // or "metadata_only"
    }
  }
}
```

**Materialization Modes**:
- `self_contained` (default for github/git/npm/file/directory): All content cached
- `metadata_only`: Only `marketplace.json` cached; Claude Code fetches plugins
- `best_effort`: Try to cache plugins, fallback to metadata if remote

### 2.5 materialize_marketplace() Function

```python
def materialize_marketplace(
    name: str,
    source: dict,
    project_cache_dir: Path,  # <project>/.claude/.scc-marketplaces/
    force_refresh: bool = False,
) -> MaterializedMarketplace:
    """
    Fetch marketplace from any source type and cache locally in PROJECT.

    Returns:
        MaterializedMarketplace with:
        - name: marketplace name
        - relative_path: path relative to project root
        - plugins: list of available plugin names
        - materialization_mode: complete | self_contained | metadata_only
        - last_updated: timestamp
    """
    cache_path = project_cache_dir / name
    source_type = source["source"]

    if source_type == "github":
        return _materialize_github(name, source, cache_path, force_refresh)
    elif source_type == "git":
        return _materialize_git(name, source, cache_path, force_refresh)
    elif source_type == "url":
        mode = source.get("materialization", "self_contained")
        return _materialize_url(name, source, cache_path, force_refresh, mode)
    elif source_type == "directory":
        # Already a directory - copy to project cache for sandbox visibility
        return _copy_directory_to_cache(name, source["path"], cache_path)
    elif source_type == "file":
        return _materialize_file(name, source, cache_path, force_refresh)
    elif source_type == "npm":
        return _materialize_npm(name, source, cache_path, force_refresh)
    else:
        raise ValidationError(f"Unknown source type: {source_type}")
```

### 2.6 Source-Specific Materialization

```python
def _materialize_github(name: str, source: dict, cache_path: Path, force: bool) -> MaterializedMarketplace:
    """
    Clone/pull GitHub repo to project cache.

    MUST create valid marketplace structure:
    cache_path/.claude-plugin/marketplace.json
    """
    repo = source["repo"]  # format: "owner/repo"
    ref = source.get("ref", "main")
    subpath = source.get("path", "")

    # Clone to temp, copy subpath to cache_path
    # CRITICAL: Ensure .claude-plugin/marketplace.json exists
    # Record commit SHA for reproducibility
    ...

def _materialize_url(
    name: str,
    source: dict,
    cache_path: Path,
    force: bool,
    mode: str = "self_contained"
) -> MaterializedMarketplace:
    """
    Fetch marketplace.json from URL and optionally download plugin contents.

    Modes:
    - self_contained: Download ALL plugin content (recommended)
    - metadata_only: Only cache marketplace.json
    - best_effort: Try to download, fallback if remote/private
    """
    url = source["url"]
    headers = source.get("headers", {})

    # Expand env vars in headers: ${VAR} → os.environ["VAR"]
    expanded_headers = {k: expand_env_vars(v) for k, v in headers.items()}

    # Fetch marketplace.json
    # If mode == "self_contained":
    #   For each plugin, fetch its source (relative paths become absolute)
    #   Rewrite plugin paths to local references
    # CRITICAL: Create .claude-plugin/marketplace.json structure
    ...

def _copy_directory_to_cache(name: str, source_path: str, cache_path: Path) -> MaterializedMarketplace:
    """
    Copy directory marketplace to project cache for sandbox visibility.

    Even 'directory' sources need copying because the original path
    may not be visible inside the Docker sandbox.
    """
    # Validate source has .claude-plugin/marketplace.json
    # Copy to cache_path
    # Return with relative_path for settings
    ...

def _materialize_git(name: str, source: dict, cache_path: Path, force: bool) -> MaterializedMarketplace:
    """Clone/pull arbitrary git URL to cache."""
    url = source["url"]
    ref = source.get("ref", "HEAD")
    subpath = source.get("path", "")
    ...
```

### 2.7 Lazy Materialization Pattern

**CRITICAL**: Don't materialize marketplaces until they're actually needed.

**Problem**: Materializing all marketplaces on `org import` has issues:
1. **Slow**: Cloning multiple GitHub repos on import is a bad DX
2. **Wasteful**: Developer might only use 1 of 5 available teams
3. **Fragile**: If any marketplace fetch fails, import fails
4. **Stale**: Caches may go stale before they're ever used

**Solution**: Lazy, on-demand materialization triggered by `scc start`.

| Command | What It Does | Materializes? |
|---------|--------------|---------------|
| `scc org import <url>` | Fetches org.json, caches to `~/.cache/scc/org_config.json` | ❌ No |
| `scc team switch <name>` | Computes effective plugins, validates config | ❌ No |
| `scc team list` | Lists available teams from cached org config | ❌ No |
| `scc start <path>` | **Materializes required marketplaces**, writes settings, launches | ✅ Yes |

**On `scc start`**:
1. Determine which marketplaces are needed (from effective plugins + extra_marketplaces)
2. Check if already materialized in `<project>/.claude/.scc-marketplaces/`
3. If missing or stale → materialize now
4. Continue with settings generation

```python
def ensure_marketplaces_materialized(
    needed: set[str],
    org_config: dict,
    project_path: Path,
    force_refresh: bool = False,
) -> dict[str, MaterializedMarketplace]:
    """
    Lazy materialization: only fetch what's needed for this project.

    Called by `scc start`, NOT by `org import` or `team switch`.
    """
    project_cache = project_path / ".claude" / ".scc-marketplaces"
    project_cache.mkdir(parents=True, exist_ok=True)

    manifest_path = project_cache / ".manifest.json"
    manifest = load_manifest(manifest_path) if manifest_path.exists() else {}

    materialized = {}
    for name in needed:
        if name in IMPLICIT_MARKETPLACES:
            continue  # Don't materialize implicit marketplaces

        source = org_config.get("marketplaces", {}).get(name, {}).get("source")
        if not source:
            raise ValidationError(f"Unknown marketplace: {name}")

        cached = manifest.get("marketplaces", {}).get(name)
        if cached and not force_refresh and not is_stale(cached):
            # Use existing cache
            materialized[name] = MaterializedMarketplace.from_cache(name, cached)
        else:
            # Materialize now
            materialized[name] = materialize_marketplace(
                name, source, project_cache, force_refresh
            )
            update_manifest(manifest_path, name, materialized[name])

    return materialized
```

**Benefits**:
- Fast `org import` (just config, no git clones)
- Project-specific materialization (respects workspace isolation)
- Automatic staleness handling
- Predictable: materialization happens exactly when launching

---

## 3. Implicit Marketplace Constants

```python
IMPLICIT_MARKETPLACES = frozenset({
    "claude-plugins-official",
    # Add future implicit marketplaces here
})
```

### 3.1 Semantic Validation: No Shadowing

```python
def validate_marketplace_names(org_marketplaces: dict[str, Any]) -> list[str]:
    """Ensure org marketplace names don't shadow implicit ones."""
    errors = []
    for name in org_marketplaces:
        if name in IMPLICIT_MARKETPLACES:
            errors.append(
                f"Marketplace name '{name}' shadows implicit marketplace. "
                f"Choose a different name."
            )
    return errors
```

---

## 4. Plugin Normalization Pipeline

### 4.1 normalize_plugin() Function

**Key Fix**: Only count org marketplaces for single-marketplace auto-assume.
Implicit marketplaces are fallback when org has ZERO marketplaces.

```python
def normalize_plugin(
    plugin: str,
    org_marketplaces: dict[str, Any],
    blocked_implicit: list[str],
) -> str:
    """
    Normalize plugin reference to full name@marketplace format.

    DX Rules:
    1. "@marketplace/plugin" or "plugin@marketplace" → validate & pass through
    2. "plugin" with 1 org marketplace → auto-assume that marketplace
    3. "plugin" with 0 org marketplaces → fallback to claude-plugins-official
    4. "plugin" with 2+ org marketplaces → ERROR: ambiguous

    Note: Implicit marketplaces do NOT count toward ambiguity.
    """
    plugin = plugin.strip()
    if not plugin:
        raise ValidationError("Plugin reference is empty")

    # Handle explicit marketplace reference
    if "@" in plugin:
        # Support both "name@marketplace" and "@marketplace/name" formats
        if plugin.startswith("@"):
            # @marketplace/name format
            parts = plugin[1:].split("/", 1)
            if len(parts) != 2 or not parts[0] or not parts[1]:
                raise ValidationError(f"Invalid plugin ref: '{plugin}'")
            marketplace, name = parts
        else:
            # name@marketplace format
            parts = plugin.rsplit("@", 1)
            if len(parts) != 2 or not parts[0] or not parts[1]:
                raise ValidationError(f"Invalid plugin ref: '{plugin}'")
            name, marketplace = parts

        # Validate marketplace exists
        if marketplace in IMPLICIT_MARKETPLACES:
            if marketplace in blocked_implicit:
                raise ValidationError(
                    f"Plugin '{plugin}' uses blocked implicit marketplace '{marketplace}'"
                )
            return f"{name}@{marketplace}"

        if marketplace not in org_marketplaces:
            raise ValidationError(f"Unknown marketplace: '{marketplace}'")

        return f"{name}@{marketplace}"

    # No @ provided: apply DX single-marketplace rule
    # IMPORTANT: Only count ORG marketplaces, not implicit ones
    if len(org_marketplaces) == 1:
        only_marketplace = next(iter(org_marketplaces.keys()))
        return f"{plugin}@{only_marketplace}"

    if len(org_marketplaces) == 0:
        # Fall back to official implicit marketplace if allowed
        official = "claude-plugins-official"
        if official in blocked_implicit:
            raise ValidationError(
                f"Plugin '{plugin}' has no marketplace and official marketplace is blocked"
            )
        return f"{plugin}@{official}"

    # Multiple org marketplaces: require explicit @
    raise ValidationError(
        f"Plugin '{plugin}' must specify @marketplace "
        f"(available: {', '.join(sorted(org_marketplaces.keys()))})"
    )
```

---

## 5. Pattern Matching Rules

### 5.1 matches_pattern() Function

Used for `blocked_plugins`, `allowed_plugins`, and `disabled_plugins`:

```python
def matches_pattern(plugin_id: str, pattern: str) -> bool:
    """
    Check if normalized plugin_id matches pattern.

    Pattern semantics:
    - With @: matches full ID (name@marketplace)
    - Without @: matches plugin name only (any marketplace)

    Uses fnmatch for wildcards, casefold() for case-insensitivity.
    """
    pattern = pattern.strip().casefold()
    plugin_id = plugin_id.casefold()

    if "@" in pattern:
        # Full ID match
        return fnmatch.fnmatch(plugin_id, pattern)
    else:
        # Name-only match: extract name from plugin_id
        name = plugin_id.split("@")[0] if "@" in plugin_id else plugin_id
        return fnmatch.fnmatch(name, pattern)


def matches_any(plugin_id: str, patterns: list[str]) -> str | None:
    """Return first matching pattern, or None if no match."""
    for pattern in patterns:
        if matches_pattern(plugin_id, pattern):
            return pattern
    return None
```

---

## 6. disabled_plugins as Patterns

**Key Fix**: `disabled_plugins` uses pattern matching, NOT normalization.

```python
def apply_disabled(
    enabled: set[str],
    disabled_patterns: list[str]
) -> tuple[set[str], list[str]]:
    """
    Remove plugins matching disabled patterns.

    Args:
        enabled: Set of normalized plugin IDs (name@marketplace)
        disabled_patterns: Patterns to remove (name-only or full ID)

    Returns:
        (remaining_enabled, removed_plugins)
    """
    remaining = set()
    removed = []

    for plugin_id in enabled:
        matched = matches_any(plugin_id, disabled_patterns)
        if matched:
            removed.append(plugin_id)
        else:
            remaining.add(plugin_id)

    return remaining, removed
```

---

## 7. Effective Plugin Computation

### 7.1 compute_effective_plugins() Function

**CRITICAL**: Normalization errors are **hard failures**, not warnings.
Invalid plugin references (typos, missing marketplace, ambiguous refs) must fail early
to prevent silent misconfiguration. Warnings are reserved for advisory info only.

```python
@dataclass
class EffectivePlugins:
    enabled: set[str]              # Normalized plugin IDs
    blocked: list[BlockedPlugin]   # Blocked with reasons
    not_allowed: list[str]         # Failed allowed_plugins check
    disabled: list[str]            # Removed by disabled_plugins
    extra_marketplaces: list[str]  # Exposed but not enabling
    # NOTE: No 'warnings' field - normalization errors are hard failures


def compute_effective_plugins(
    org_config: dict,
    team_name: str,
) -> EffectivePlugins:
    """
    Compute final plugin set for a team.

    Pipeline:
    1. Normalize defaults.enabled_plugins → HARD ERROR on invalid
    2. Normalize profile.additional_plugins → HARD ERROR on invalid
    3. Merge: base + additional
    4. Apply disabled_plugins (pattern matching)
    5. Check allowed_plugins (if set, must match)
    6. Check blocked_plugins (remove matches)
    7. Collect extra_marketplaces

    Raises:
        ValidationError: If ANY plugin reference cannot be normalized.
                        This is intentional - invalid refs must fail early.
    """
    org_marketplaces = org_config.get("marketplaces", {})
    security = org_config.get("security", {})
    defaults = org_config.get("defaults", {})
    profile = org_config.get("profiles", {}).get(team_name, {})

    blocked_implicit = (
        list(IMPLICIT_MARKETPLACES)
        if security.get("block_implicit_marketplaces")
        else []
    )

    # Step 1-3: Normalize and merge
    # FAIL FAST on invalid plugin references - don't collect as warnings
    enabled = set()

    for plugin_ref in defaults.get("enabled_plugins", []):
        # ValidationError propagates - this is intentional
        normalized = normalize_plugin(plugin_ref, org_marketplaces, blocked_implicit)
        enabled.add(normalized)

    for plugin_ref in profile.get("additional_plugins", []):
        # ValidationError propagates - this is intentional
        normalized = normalize_plugin(plugin_ref, org_marketplaces, blocked_implicit)
        enabled.add(normalized)

    # Step 4: Apply disabled_plugins (pattern matching)
    disabled_patterns = profile.get("disabled_plugins", [])
    enabled, disabled = apply_disabled(enabled, disabled_patterns)

    # Step 5: Check allowed_plugins (if configured)
    allowed_patterns = defaults.get("allowed_plugins", [])
    not_allowed = []
    if allowed_patterns:
        remaining = set()
        for plugin_id in enabled:
            if matches_any(plugin_id, allowed_patterns):
                remaining.add(plugin_id)
            else:
                not_allowed.append(plugin_id)
        enabled = remaining

    # Step 6: Check blocked_plugins
    blocked_patterns = security.get("blocked_plugins", [])
    blocked = []
    remaining = set()
    for plugin_id in enabled:
        matched_pattern = matches_any(plugin_id, blocked_patterns)
        if matched_pattern:
            blocked.append(BlockedPlugin(
                plugin_id=plugin_id,
                reason=f"Matched blocked pattern: {matched_pattern}",
                pattern=matched_pattern,
            ))
        else:
            remaining.add(plugin_id)
    enabled = remaining

    # Step 7: Collect extra_marketplaces
    extra = set(defaults.get("extra_marketplaces", []))
    extra.update(profile.get("extra_marketplaces", []))

    return EffectivePlugins(
        enabled=enabled,
        blocked=blocked,
        not_allowed=not_allowed,
        disabled=disabled,
        extra_marketplaces=sorted(extra),
    )
```

---

## 8. Settings Rendering

### 8.1 Claude Code extraKnownMarketplaces Format

Per Claude Code docs, `extraKnownMarketplaces` supports ONLY:
- `github` (repo, optional ref/path)
- `git` (url, optional ref/path)
- `directory` (path)

**NOT supported**: `url`, `npm`, `file` in `extraKnownMarketplaces`.

**Solution**: Always emit as `directory` sources pointing to materialized cache.

### 8.2 render_settings() Function

```python
def render_settings(
    effective: EffectivePlugins,
    materialized: dict[str, MaterializedMarketplace],
) -> dict:
    """
    Render to Claude Code settings.local.json format.

    IMPORTANT: All marketplaces are emitted as directory sources
    with RELATIVE paths (for sandbox compatibility).
    """
    extra_known = {}

    # Determine which marketplaces are needed
    needed_marketplaces = set()

    # From enabled plugins
    for plugin_id in effective.enabled:
        if "@" in plugin_id:
            marketplace = plugin_id.split("@")[1]
            if marketplace not in IMPLICIT_MARKETPLACES:
                needed_marketplaces.add(marketplace)

    # From extra_marketplaces
    for name in effective.extra_marketplaces:
        if name not in IMPLICIT_MARKETPLACES:
            needed_marketplaces.add(name)

    # Build extraKnownMarketplaces with directory sources
    # CRITICAL: Use RELATIVE paths for sandbox compatibility
    for name in sorted(needed_marketplaces):
        if name in materialized:
            # Use relative_path, NOT absolute cache_path
            relative_path = materialized[name].relative_path  # e.g., ".claude/.scc-marketplaces/internal-plugins"
            extra_known[name] = {
                "source": {
                    "source": "directory",
                    "path": relative_path
                }
            }

    # Build enabledPlugins object
    enabled_plugins = {
        plugin_id: True
        for plugin_id in sorted(effective.enabled)
    }

    settings = {}
    if extra_known:
        settings["extraKnownMarketplaces"] = extra_known
    if enabled_plugins:
        settings["enabledPlugins"] = enabled_plugins

    return settings
```

### 8.3 Example Output

**IMPORTANT**: Paths are RELATIVE for sandbox compatibility.

```json
{
  "extraKnownMarketplaces": {
    "internal-plugins": {
      "source": {
        "source": "directory",
        "path": ".claude/.scc-marketplaces/internal-plugins"
      }
    },
    "team-shared": {
      "source": {
        "source": "directory",
        "path": ".claude/.scc-marketplaces/team-shared"
      }
    }
  },
  "enabledPlugins": {
    "code-standards@internal-plugins": true,
    "api-tools@internal-plugins": true
  }
}
```

**Why relative paths?**
- Sandbox mounts project at `/workspace`
- Relative paths resolve correctly inside container
- Absolute paths like `/Users/dev/...` don't exist in sandbox

---

## 9. Non-Destructive Merge Strategy

### 9.1 File Locations

```
<project>/.claude/settings.local.json    # Claude Code settings
<project>/.claude/.scc-managed.json      # SCC tracking metadata
```

### 9.2 .scc-managed.json Schema

```json
{
  "version": 1,
  "team": "backend",
  "last_updated": "2025-12-25T10:30:00Z",
  "managed_marketplaces": ["internal-plugins", "team-shared"],
  "managed_plugins": [
    "code-standards@internal-plugins",
    "api-tools@internal-plugins"
  ]
}
```

### 9.3 Merge Algorithm

```python
def merge_settings(
    existing: dict,
    computed_settings: dict,
    managed: ManagedState,
) -> tuple[dict, ManagedState]:
    """
    Merge computed settings with existing, preserving user additions.

    Algorithm:
    1. Remove previously-managed entries (from .scc-managed.json)
    2. Add new computed entries
    3. Preserve any user-added entries (not in old managed list)
    """
    merged = copy.deepcopy(existing)

    # Remove old managed marketplaces
    if "extraKnownMarketplaces" in merged:
        for name in managed.managed_marketplaces:
            merged["extraKnownMarketplaces"].pop(name, None)

    # Remove old managed plugins
    if "enabledPlugins" in merged:
        for plugin_id in managed.managed_plugins:
            merged["enabledPlugins"].pop(plugin_id, None)

    # Add new computed entries
    if "extraKnownMarketplaces" in computed_settings:
        merged.setdefault("extraKnownMarketplaces", {})
        merged["extraKnownMarketplaces"].update(
            computed_settings["extraKnownMarketplaces"]
        )

    if "enabledPlugins" in computed_settings:
        merged.setdefault("enabledPlugins", {})
        merged["enabledPlugins"].update(computed_settings["enabledPlugins"])

    # Clean up empty sections
    if not merged.get("extraKnownMarketplaces"):
        merged.pop("extraKnownMarketplaces", None)
    if not merged.get("enabledPlugins"):
        merged.pop("enabledPlugins", None)

    # Build new managed state
    new_managed = ManagedState(
        version=1,
        team=managed.team,
        last_updated=datetime.utcnow().isoformat() + "Z",
        managed_marketplaces=list(
            computed_settings.get("extraKnownMarketplaces", {}).keys()
        ),
        managed_plugins=list(
            computed_settings.get("enabledPlugins", {}).keys()
        ),
    )

    return merged, new_managed
```

---

## 10. Light Governance Model

### 10.1 --allow-blocked Flag

```bash
# Normal: blocked plugin causes warning
$ scc start .
WARNING: Plugin 'dangerous-tool@internal' is blocked by organization policy
  Matched pattern: dangerous-*

# Override with explicit flag
$ scc start . --allow-blocked dangerous-tool
AUDIT: User override for blocked plugin 'dangerous-tool@internal'
```

### 10.2 Audit Logging

Overrides are logged to `~/.cache/scc/audit.jsonl`:

```json
{
  "timestamp": "2025-12-25T10:30:00Z",
  "event": "blocked_plugin_override",
  "user": "developer@sundsvall.se",
  "plugin": "dangerous-tool@internal",
  "matched_pattern": "dangerous-*",
  "workspace": "/path/to/project",
  "team": "backend"
}
```

---

## 11. End-to-End Flow

### 11.1 Org Admin Responsibilities

Org admin owns:
1. **org.json** (the SCC org config)
2. **Security boundaries** (blocked_plugins, allowed_plugins)
3. **Marketplace registry pointers** (where teams live + approved externals)

Org admin does NOT curate team content - just ensures each team marketplace exists.

### 11.2 Team Workflow (Autonomy)

Each team maintains their own bootstrap plugin in their own folder/repo:
- Maintain `marketplace.json` + plugin folders
- Version changes (tag releases recommended)
- Update content freely (CLAUDE.md, agents, skills, MCP configs, hooks, commands)

Teams add external plugins by:
1. If org already defines a marketplace → reference plugins from it
2. If new external needed → PR org config to add it (org admin approves source)

### 11.3 Developer Flow

```bash
# 1. One-time: Import org config (source-agnostic)
$ scc org import https://config.example.com/org.json
# OR
$ scc org import git@gitlab.internal:ai/scc-config.git
# OR
$ scc org import company/scc-org-config  # GitHub shorthand

Imported organization: Example Corp (5 teams available)
Saved to ~/.cache/scc/org_config.json

# 2. Pick team (validates config, no materialization)
$ scc team switch backend
Switched to team: backend
Effective plugins:
  • code-standards (from defaults)
  • api-tools (from team profile)
Note: Marketplaces materialize on first `scc start`

# 3. Start project (materializes what's needed)
$ cd ~/projects/my-service
$ scc start .
Materializing 2 marketplaces...
  ✓ internal-plugins (git clone)
  ✓ shared (git clone)
Writing .claude/settings.local.json
Starting Claude Code...

# 4. Later: SCC notices updates available (non-blocking notification)
$ scc start .
┌─────────────────────────────────────────────────────┐
│  ℹ️  Updates available — run: scc org update        │
└─────────────────────────────────────────────────────┘
Using cached marketplaces...
Starting Claude Code...

# 5. Developer chooses when to update (explicit, not automatic)
$ scc org update
Fetching org config...
  ✓ 2 profiles updated
Checking marketplaces...
  ✓ internal-plugins: v2025.01 → v2025.02 (will update on next start)
  ✓ shared: unchanged

$ scc start .
Updating marketplace: internal-plugins...
  ✓ internal-plugins (v2025.02)
Starting Claude Code...
```

### 11.4 What SCC Does on `start`

1. Computes effective plugins for chosen team
2. Applies `allowed_plugins` + `blocked_plugins`
3. **Materializes** required marketplaces to cache (if not already cached)
4. Writes:
   - `.claude/settings.local.json` (only SCC-managed parts)
   - `.claude/.scc-managed.json` (tracks what SCC wrote)
5. Launches Claude Code

### 11.5 What Claude Code Does

1. Prompts **Trust this folder** (first time)
2. Prompts **Install marketplaces** / **Install plugins** (first time)
3. After consent, smooth on subsequent runs

### 11.6 Personal Customization

Developers can add personal settings/plugins:
- SCC's merge strategy preserves anything not in `.scc-managed.json`
- Team switching removes only SCC-managed entries

### 11.7 Updates

**Design Principle:** Updates are **manual and explicit**. SCC notifies but never auto-updates.

#### Staleness Detection

On every `scc start`, SCC checks:
1. **Org config age**: Compare cached timestamp vs TTL (default: 24h)
2. **Marketplace freshness**: Compare cached manifest vs expected

#### Non-Blocking Notification

If updates are available, SCC displays a notification **but continues with cached versions**:

```bash
$ scc start .
┌─────────────────────────────────────────────────────┐
│  ℹ️  Updates available — run: scc org update        │
└─────────────────────────────────────────────────────┘
Starting Claude Code with team: backend-team...
```

#### Update Command

```bash
# Full update: org config + all marketplaces
$ scc org update

# Config only (skip marketplace refresh)
$ scc org update --config-only

# Specific marketplace
$ scc org update --marketplace internal-plugins

# Force refresh even if fresh
$ scc org update --force
```

**Example output:**
```bash
$ scc org update
Fetching org config...
  ✓ org config (updated: new marketplace added)
Updating marketplaces...
  ✓ internal-plugins (unchanged)
  ✓ team-shared (updated: v2.1.0 → v2.2.0)
  ✓ new-marketplace (added)
```

#### Why Manual Updates?

| Concern | Solution |
|---------|----------|
| CI reproducibility | Pinned versions, no surprise updates |
| Offline work | Cached config works without network |
| Developer control | Update when ready, not mid-task |
| Audit trail | Explicit update commands in history |

---

## 12. CLI Commands

### 12.1 Organization Commands

```bash
scc org import <source>     # Import org config (URL/file/GitHub)
scc org update              # Refresh cached org config + marketplaces
scc org validate <file>     # Validate org config against schema
scc org schema              # Print bundled JSON schema
```

### 12.2 Team Commands

```bash
scc team list               # List available teams
scc team switch <name>      # Switch to team (updates settings)
scc team show               # Show current team details
```

### 12.3 Config Commands

```bash
scc config explain          # Show effective config with sources
scc config explain --field plugins  # Focus on specific field
```

### 12.4 Start Command

```bash
scc start <path>            # Start with computed settings
scc start <path> --dry-run  # Preview without writing
scc start <path> --allow-blocked <pattern>  # Override blocked
```

---

## 13. Implementation Phases

### Phase 1: Core Plugin Management (Current Scope)

#### Scope Boundary

| Source Type | Phase 1 | Notes |
|-------------|---------|-------|
| `directory` | ✅ | Local filesystem paths |
| `github` | ✅ | `owner/repo` shorthand via `git clone` |
| `git` | ✅ | Full git URLs via `git clone` |
| `url` (metadata_only) | ✅ | Fetch manifest, Claude installs plugins |
| `url` (self_contained) | ✅ | Fetch + cache all plugin content |
| `npm` | ❌ Phase 2 | Requires npm registry integration |
| `file` | ❌ Phase 2 | Local file:// URLs |
| Remote plugin fetching | ❌ Phase 2 | Plugins referencing external URLs |

**Git Implementation Notes:**
- Use subprocess `git clone` (not library bindings)
- Don't assume branch names; record commit SHA for reproducibility
- Support both HTTPS and SSH URLs

**Deliverables**:
- [ ] Schema validation with marketplace support
- [ ] Semantic validation: no shadowing implicit marketplaces
- [ ] `normalize_plugin()` with DX logic
- [ ] `matches_pattern()` for all pattern matching
- [ ] `apply_disabled()` using patterns
- [ ] `compute_effective_plugins()` with allowed_plugins enforcement
- [ ] Marketplace materialization (github, git, url, directory)
- [ ] `render_settings()` emitting directory sources
- [ ] `.claude/.scc-managed.json` tracking
- [ ] Non-destructive merge algorithm
- [ ] `scc org import/update/validate` commands
- [ ] `scc team list/switch/show` commands
- [ ] `scc config explain` with plugin display
- [ ] `scc start` with settings generation

**Out of Scope for Phase 1**:
- npm/file source types (low priority)
- Global settings management
- Marketplace plugin discovery/listing UI
- Plugin integrity verification

### Phase 2: Enhanced Features (Future)

- npm/file source materialization
- `scc plugins list` - discover available plugins
- Plugin integrity checks
- Global settings support
- Marketplace caching with ETag/freshness checks

---

## 14. Example Org Config

```json
{
  "$schema": "https://scc-cli.dev/schemas/org-v1.json",
  "schema_version": "1.0.0",
  "organization": {
    "name": "Sundsvalls kommun",
    "id": "sundsvall",
    "contact": "devops@sundsvall.se"
  },
  "marketplaces": {
    "internal-plugins": {
      "source": {
        "source": "url",
        "url": "https://plugins.sundsvall.se/marketplace.json",
        "headers": {
          "Authorization": "Bearer ${SUNDSVALL_PLUGIN_TOKEN}"
        }
      },
      "autoUpdate": true,
      "description": "Internal Sundsvall plugins"
    },
    "team-shared": {
      "source": {
        "source": "github",
        "repo": "sundsvall-kommun/claude-plugins",
        "ref": "v2.1.0",
        "path": "plugins"
      }
    }
  },
  "security": {
    "blocked_plugins": [
      "untrusted-*",
      "*@unknown-marketplace"
    ],
    "block_implicit_marketplaces": false
  },
  "defaults": {
    "enabled_plugins": [
      "code-standards",
      "security-scanner"
    ],
    "allowed_plugins": ["*"],
    "extra_marketplaces": ["team-shared"]
  },
  "profiles": {
    "backend": {
      "description": "Backend development team",
      "additional_plugins": [
        "api-tools",
        "db-helpers"
      ]
    },
    "frontend": {
      "description": "Frontend development team",
      "additional_plugins": [
        "component-lib",
        "a11y-checker"
      ],
      "disabled_plugins": [
        "db-helpers"
      ]
    },
    "devops": {
      "description": "DevOps and infrastructure team",
      "additional_plugins": [
        "infra-tools",
        "k8s-helper"
      ],
      "extra_marketplaces": ["internal-plugins"]
    }
  }
}
```

---

## 15. Testing Strategy

### Unit Tests

```python
class TestNormalizePlugin:
    def test_explicit_marketplace_passthrough(self): ...
    def test_at_prefix_format_supported(self): ...
    def test_single_org_marketplace_auto_assume(self): ...
    def test_zero_org_marketplaces_fallback_to_official(self): ...
    def test_multiple_org_marketplaces_requires_explicit(self): ...
    def test_implicit_marketplace_not_counted_for_ambiguity(self): ...

class TestMatchesPattern:
    def test_at_pattern_matches_full_id(self): ...
    def test_name_pattern_matches_any_marketplace(self): ...
    def test_wildcard_matching(self): ...
    def test_case_insensitive_casefold(self): ...

class TestApplyDisabled:
    def test_name_pattern_removes_from_any_marketplace(self): ...
    def test_full_id_pattern_exact_match(self): ...

class TestComputeEffectivePlugins:
    def test_base_plus_additional(self): ...
    def test_disabled_removes_matching(self): ...
    def test_allowed_filters_result(self): ...
    def test_blocked_filters_result(self): ...

class TestMaterializeMarketplace:
    def test_github_source_clones_repo(self): ...
    def test_url_source_with_headers(self): ...
    def test_directory_source_validates_path(self): ...
    def test_caches_with_manifest(self): ...

class TestRenderSettings:
    def test_emits_directory_sources_only(self): ...
    def test_uses_cache_paths(self): ...
    def test_builtin_marketplace_not_written(self): ...

class TestSemanticValidation:
    def test_org_marketplace_cannot_shadow_implicit(self): ...

class TestNonDestructiveMerge:
    def test_preserves_user_additions(self): ...
    def test_removes_old_managed_entries(self): ...
    def test_team_switch_clean_handoff(self): ...
```

### Integration Tests

```python
class TestEndToEndFlow:
    def test_org_import_materializes_marketplaces(self): ...
    def test_team_switch_updates_settings(self): ...
    def test_start_writes_correct_directory_sources(self): ...
    def test_blocked_plugin_warning(self): ...
    def test_allow_blocked_override(self): ...
```

### Path Resolution Smoke Tests

Critical tests to verify Docker sandbox compatibility:

```python
class TestPathResolutionForSandbox:
    """Verify paths work inside Docker sandbox where project is mounted at /workspace."""

    def test_settings_use_relative_paths(self):
        """settings.local.json must NOT contain absolute paths."""
        settings = render_settings(...)
        for source in settings["extraKnownMarketplaces"]:
            if source["type"] == "directory":
                path = source["directory"]["path"]
                assert not path.startswith("/"), f"Absolute path found: {path}"
                assert not path.startswith("~"), f"Home path found: {path}"

    def test_marketplace_cache_under_project(self):
        """Materialized marketplaces must be in project directory."""
        cache_path = get_marketplace_cache_path(project_path)
        assert str(cache_path).startswith(str(project_path))
        assert ".claude/.scc-marketplaces" in str(cache_path)

    def test_relative_path_resolves_in_sandbox(self):
        """Simulate sandbox mount and verify path resolution."""
        # In sandbox: project is at /workspace
        # Path in settings: ".claude/.scc-marketplaces/internal-plugins"
        # Should resolve to: /workspace/.claude/.scc-marketplaces/internal-plugins
        sandbox_cwd = Path("/workspace")
        relative_path = ".claude/.scc-marketplaces/internal-plugins"
        resolved = sandbox_cwd / relative_path
        assert resolved == Path("/workspace/.claude/.scc-marketplaces/internal-plugins")
```

---

## Appendix A: Decision Log

| Decision | Rationale | Alternatives Considered |
|----------|-----------|------------------------|
| Materialize to directories | Claude Code only supports github/git/directory in extraKnownMarketplaces | Emit url sources (won't work per docs) |
| `headers` not `httpHeaders` | Claude Code docs use `headers` | Use `httpHeaders` (wrong) |
| `directory.path` not `directory` | Claude Code schema uses nested `path` | Use `directory` field (wrong) |
| DX: only count org marketplaces | Prevents 1+implicit=2 ambiguity trap | Count all (worse UX) |
| disabled_plugins as patterns | Allows `["java-assist"]` without @ | Require normalization (error-prone) |
| Enforce allowed_plugins | Complete security model | Only blocked_plugins (incomplete) |
| No shadowing implicit names | Prevent confusing overwrites | Allow shadowing (confusing) |
| Metadata in `.claude/` | Keep repo root clean | Project root (cluttered) |

---

## Appendix B: Claude Code Compatibility Notes

### extraKnownMarketplaces Supported Sources

Per [Claude Code settings docs](https://code.claude.com/docs/en/settings):

| Source Type | Supported | Fields |
|-------------|-----------|--------|
| `github` | ✅ | `repo`, `ref`, `path` |
| `git` | ✅ | `url`, `ref`, `path` |
| `directory` | ✅ | `path` |
| `url` | ❌ | N/A (enterprise only in strictKnownMarketplaces) |
| `npm` | ❌ | N/A |
| `file` | ❌ | N/A |

**This is why we materialize everything to directories.**

### URL Auth Format

```json
// CORRECT (per docs)
{
  "source": "url",
  "url": "https://...",
  "headers": { "Authorization": "Bearer ..." }
}

// WRONG
{
  "source": "url",
  "url": "https://...",
  "httpHeaders": { ... }
}
```

### Directory Source Format

```json
// CORRECT (per docs)
{
  "source": "directory",
  "path": "/absolute/path/to/marketplace"
}

// WRONG
{
  "source": "directory",
  "directory": "/path"
}
```

---

## Appendix C: Docker Sandbox Integration

### How Docker Sandbox Works

SCC runs Claude Code inside Docker using the `docker sandbox` plugin:

```bash
# SCC launches Claude Code via docker sandbox
docker sandbox run -w <project_path> claude
```

**Key Behaviors** (from Docker Sandbox documentation):

1. **Workspace Mount**: The `-w <path>` flag mounts `<path>` as the workspace
   - The project directory becomes visible at `/workspace` inside the container
   - Files inside project are accessible; files outside are NOT

2. **No Additional Mounts by Default**: The sandbox doesn't mount `~/.cache/`, `~/.config/`, or other home directories
   - This is why marketplaces MUST be project-local
   - Volume mounts (`-v`) require special flags and recreating the sandbox

3. **Persistence**: Sandbox state persists across invocations
   - Files written to workspace persist
   - Claude Code settings in `.claude/` persist

### Why This Matters for Marketplaces

```
# ❌ FAILS: Path not visible in sandbox
~/.cache/scc/marketplaces/internal-plugins
↓ Claude Code tries to access
/Users/dev/.cache/scc/marketplaces/internal-plugins  → NOT MOUNTED

# ✅ WORKS: Project-local path is visible
<project>/.claude/.scc-marketplaces/internal-plugins
↓ Claude Code accesses
/workspace/.claude/.scc-marketplaces/internal-plugins → VISIBLE
```

### SCC's Docker Integration Pattern

```python
def start_session(project_path: Path, team_name: str) -> None:
    """
    SCC's start flow ensures sandbox compatibility.

    1. Compute effective plugins
    2. Materialize marketplaces INTO project (not ~/.cache/)
    3. Write settings with RELATIVE paths
    4. Launch via docker sandbox
    """
    # Step 1: Compute
    effective = compute_effective_plugins(org_config, team_name)

    # Step 2: Materialize to PROJECT-LOCAL cache
    cache_dir = project_path / ".claude" / ".scc-marketplaces"
    needed = get_needed_marketplaces(effective)
    materialized = ensure_marketplaces_materialized(needed, org_config, project_path)

    # Step 3: Render settings with RELATIVE paths
    # Settings MUST use paths like ".claude/.scc-marketplaces/internal-plugins"
    # NOT absolute paths like "/Users/dev/project/.claude/..."
    settings = render_settings(effective, materialized)

    # Step 4: Write and launch
    write_settings(project_path / ".claude" / "settings.local.json", settings)
    subprocess.run([
        "docker", "sandbox", "run",
        "-w", str(project_path),
        "claude"
    ])
```

### Path Resolution in Settings

```json
{
  "extraKnownMarketplaces": {
    "internal-plugins": {
      "source": {
        "source": "directory",
        "path": ".claude/.scc-marketplaces/internal-plugins"
      }
    }
  }
}
```

**NOT this** (absolute path breaks in sandbox):
```json
{
  "extraKnownMarketplaces": {
    "internal-plugins": {
      "source": {
        "source": "directory",
        "path": "/Users/dev/project/.claude/.scc-marketplaces/internal-plugins"
      }
    }
  }
}
```

### Volume Mount Alternative (Not Recommended)

If you absolutely need external paths, Docker sandbox supports volume mounts:

```bash
docker sandbox run -w /path/to/project \
    -v /shared/marketplaces:/shared/marketplaces \
    claude
```

**However, this is NOT recommended because**:
- Requires recreating the sandbox (`docker sandbox rm claude` first)
- Makes settings non-portable (different machines have different paths)
- Adds complexity that project-local caching avoids

**SCC's project-local pattern is simpler and always works.**

---

## Appendix D: Validation Consensus

**Models Consulted**: GPT-5.2, Gemini-3-Pro-Preview

**Revision 5 Key Changes** (current):
1. **marketplace.json schema fixes**: Added required `owner.name`, moved description to `metadata.description`, renamed `path` to `source`
2. **Directory structure correction**: `plugin.json` lives at `<plugin>/.claude-plugin/plugin.json`, functional dirs at plugin root
3. **Vocabulary clarification**: Distinguished "marketplace source" (github/git/directory) from "plugin source" (relative path)
4. **Source-agnostic design**: Documented SCC works identically with GitLab, GitHub, URL, or local sources
5. **Manual updates**: `scc start` notifies but never auto-updates; developer runs `scc org update` explicitly
6. **Phase 1 scope table**: Explicit inclusion/exclusion of source types with git implementation notes
7. **Path resolution smoke tests**: Added tests verifying relative paths work in Docker sandbox
8. **Monorepo layout example**: Appendix E shows multi-team single-repo organization pattern

**Revision 4 Key Changes**:
1. **Project-local caching**: Marketplaces cached in `<project>/.claude/.scc-marketplaces/` for sandbox visibility
2. **Valid marketplace structure**: Materialized dirs MUST contain `.claude-plugin/marketplace.json`
3. **Relative paths in settings**: All paths emitted as relative (e.g., `.claude/.scc-marketplaces/...`)
4. **URL materialization modes**: `self_contained`, `metadata_only`, `best_effort` options
5. **Hard failures for normalization**: Invalid plugin refs raise errors, not warnings
6. **Lazy materialization**: Only materialize on `scc start`, not on `org import`
7. **Docker sandbox appendix**: Documented integration patterns and path visibility

**Revision 3 Key Changes**:
1. **Materialization strategy**: All sources → local directories → emit as `directory` to Claude Code
2. **`headers` not `httpHeaders`**: Fixed per Claude Code docs
3. **`directory.path`**: Fixed per Claude Code docs
4. **`extraKnownMarketplaces` limitations**: Only github/git/directory supported (not url/npm/file)
5. **Cache manifest**: Track source → cache mappings for updates
6. **End-to-end flow**: Documented org admin → team → developer responsibilities

---

## Appendix E: Monorepo Layout Example

Organizations can host multiple team marketplaces in a single repository:

```
sundsvall-claude-plugins/              # GitHub repo: sundsvall-kommun/claude-plugins
├── CODEOWNERS                         # Governance: who can approve changes
├── README.md
├── marketplaces/
│   ├── backend-team/                  # One marketplace per team
│   │   ├── .claude-plugin/
│   │   │   └── marketplace.json       # Marketplace manifest
│   │   └── plugins/
│   │       ├── api-tools/
│   │       │   ├── .claude-plugin/
│   │       │   │   └── plugin.json
│   │       │   ├── commands/
│   │       │   └── skills/
│   │       └── db-helpers/
│   │           └── ...
│   │
│   ├── frontend-team/                 # Another team's marketplace
│   │   ├── .claude-plugin/
│   │   │   └── marketplace.json
│   │   └── plugins/
│   │       └── ui-components/
│   │           └── ...
│   │
│   └── shared/                        # Org-wide shared plugins
│       ├── .claude-plugin/
│       │   └── marketplace.json
│       └── plugins/
│           └── code-standards/
│               └── ...
```

**org.json configuration** for this layout:

```json
{
  "defaults": {
    "marketplaces": [
      {
        "name": "shared",
        "source": {
          "source": "github",
          "repo": "sundsvall-kommun/claude-plugins",
          "path": "marketplaces/shared"
        }
      }
    ]
  },
  "profiles": {
    "backend-team": {
      "marketplaces": [
        {
          "name": "backend-plugins",
          "source": {
            "source": "github",
            "repo": "sundsvall-kommun/claude-plugins",
            "path": "marketplaces/backend-team"
          }
        }
      ]
    },
    "frontend-team": {
      "marketplaces": [
        {
          "name": "frontend-plugins",
          "source": {
            "source": "github",
            "repo": "sundsvall-kommun/claude-plugins",
            "path": "marketplaces/frontend-team"
          }
        }
      ]
    }
  }
}
```

**Benefits**:
- Single repo to manage, single CI pipeline
- CODEOWNERS can enforce team-level approval for their plugins
- Shared plugins available to all teams via `defaults.marketplaces`
- Teams can't modify each other's plugins without approval
