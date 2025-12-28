# Governance Model

SCC enforces a 3-layer configuration system. Organizations define security boundaries. Teams add tools within those boundaries. Projects customize further if their team allows it.

## Trust Model

There are **two sources** of MCP servers in a Claude Code environment:

### 1. SCC-Managed MCP Servers (org/team/project config)

These are controlled by SCC governance:
- `blocked_mcp_servers` patterns apply ✓
- `allow_stdio_mcp` gate applies ✓ (for SCC-managed stdio declarations)
- `allowed_stdio_prefixes` validation applies ✓
- Delegation controls who can add them ✓

**Example:** Finance team wants to add `jira-api` (HTTP/SSE) to reach an internal service → delegation controls this.

### 2. Plugin-Bundled MCP Servers (`.mcp.json` inside plugins)

SCC does not fetch or inspect plugin contents. These are **not** governed by `blocked_mcp_servers`.
- To restrict, block the entire plugin
- Treat plugins as atomic trust units

**Example:** Plugin "cool-dev-tools" bundles an MCP server → SCC can't partially strip it; you either allow the plugin or block it.

**Implication:** If you allow a plugin, you implicitly allow its bundled MCP servers.

## The Three Layers

```
Organization (org_config.json)
    ↓ security blocks + defaults
Team Profile (profiles section)
    ↓ additional plugins/servers
Project (.scc.yaml in repo root)
    ↓ project-specific additions
```

Each layer can add to the previous, but cannot remove security restrictions.

## Security Boundaries

Organizations define patterns that block plugins, MCP servers, or Docker base images globally:

```yaml
security:
  blocked_plugins:
    - "malicious-*"
    - "untrusted-tool"
  blocked_mcp_servers:
    - "*.untrusted.com"
    - "insecure-api"
  blocked_base_images:
    - "*:latest"
    - "docker.io/*"
```

These use glob patterns (fnmatch) with case-insensitive matching. If a plugin matches `malicious-*`, no team or project can use it. This is absolute.

Untagged images are normalized to `:latest` before matching. `ubuntu` becomes `ubuntu:latest`, which would be blocked by `*:latest`.

## Plugin Allowlist (`allowed_plugins`)

The `defaults.allowed_plugins` field controls which plugins can be enabled. This is a **governance whitelist** (what's permitted), not to be confused with `enabled_plugins` (what's active).

### Semantics

| Value | Meaning | Effect |
|-------|---------|--------|
| **Missing/undefined** | Unrestricted | All plugins allowed (runtime default) |
| **`[]` (empty array)** | Deny all | No plugins allowed - explicit lockdown |
| **`["*"]`** | Explicit unrestricted | All plugins allowed via fnmatch wildcard |
| **Patterns** | Specific whitelist | Only matching plugins allowed |

### Examples

```yaml
# Unrestricted - all plugins allowed (implicit default)
defaults: {}

# Explicit unrestricted - all plugins allowed (explicit configuration)
defaults:
  allowed_plugins: ["*"]

# Deny all - no plugins allowed (lockdown mode)
defaults:
  allowed_plugins: []

# Specific whitelist - only matching plugins allowed
defaults:
  allowed_plugins:
    - "*@internal"           # Any plugin from internal marketplace
    - "code-review@*"        # code-review from any marketplace
    - "approved-tool@official"  # Specific plugin from specific marketplace
```

### Invariant Rules

SCC enforces two invariants at config validation:

1. **`enabled ⊆ allowed`**: Enabled plugins must be in the allowed list
2. **`enabled ∩ blocked = ∅`**: Enabled plugins must not be blocked by security

If these invariants are violated, config validation fails with a clear error message.

### Federated Team Exception

Federated teams (those with `config_source`) **skip `allowed_plugins` filtering**. They are trusted via `trust` grants instead. This enables team autonomy while maintaining security through marketplace source patterns.

## Delegation

Organizations control what teams can add. Teams control what projects can add.

### Organization to Team

```yaml
delegation:
  teams:
    allow_additional_plugins: ["*"]        # all teams can add plugins
    allow_additional_mcp_servers: ["finance", "platform"]  # only these teams
```

If a team isn't listed, they cannot add that resource type. They can still use whatever the organization provides by default.

### Team to Project

Each team profile controls whether projects can add resources:

```yaml
profiles:
  finance:
    delegation:
      allow_project_overrides: true   # projects can add within team's scope

  platform:
    delegation:
      allow_project_overrides: false  # projects use team config only
```

A project can only add resources if:
1. The team has `allow_project_overrides: true`
2. The team itself is delegated for that resource type
3. The resource doesn't match any security block

### Federated Teams (External Config Sources)

Teams can store their configuration in an external repository instead of inline in the org config. This enables team leads to manage their plugins independently:

```yaml
profiles:
  platform:
    description: "Platform team with external config"
    config_source:
      source: github
      owner: "myorg"
      repo: "platform-team-config"
      branch: "main"
    trust:
      inherit_org_marketplaces: true
      allow_additional_marketplaces: true
      marketplace_source_patterns:
        - "github.com/myorg/**"
```

#### Config Source Types

| Type | Example | Use Case |
|------|---------|----------|
| `github` | `owner: "org", repo: "config"` | GitHub repositories (public/private) |
| `git` | `url: "git@gitlab.com:org/config.git"` | Any Git hosting (GitLab, Bitbucket) |
| `url` | `url: "https://configs.example.com/team.json"` | HTTPS-hosted config files |

#### Trust Grants

Organizations control what federated teams can do via trust grants:

| Field | Default | Description |
|-------|---------|-------------|
| `inherit_org_marketplaces` | `true` | Team can use marketplaces defined in org config |
| `allow_additional_marketplaces` | `false` | Team can define their own marketplace sources |
| `marketplace_source_patterns` | `[]` | URL patterns for allowed team marketplace sources |

Trust validation uses two layers:
1. **Permission Check**: Does `allow_additional_marketplaces` allow team to define marketplaces?
2. **Source Validation**: Does each marketplace URL match `marketplace_source_patterns`?

#### URL Pattern Matching

Patterns support glob syntax with `**` for path matching:

| Pattern | Matches |
|---------|---------|
| `github.com/myorg/**` | Any repo under myorg GitHub organization |
| `*.internal.com/**` | Any path on any internal subdomain |
| `github.com/myorg/approved-*` | Only repos starting with "approved-" |

#### Marketplace Name Collisions

Team-defined marketplaces cannot conflict with:
- **Org marketplaces**: Names defined in org config's `marketplaces` section
- **Implicit marketplaces**: `claude-plugins-official`

If a collision is detected, the config is rejected with a clear error message.

#### When inherit_org_marketplaces is false

If a team sets `inherit_org_marketplaces: false`, they won't have access to org-defined marketplaces. This creates a potential conflict if `defaults.enabled_plugins` references plugins from those marketplaces.

SCC validates this at config resolution time and rejects configurations where:
- Team has `inherit_org_marketplaces: false`
- Org defaults reference plugins from org marketplaces (e.g., `plugin@shared-marketplace`)

**Fix**: Either set `inherit_org_marketplaces: true` or remove conflicting plugins from org defaults.

## What Gets Merged

### Plugins

Plugins accumulate. If org defaults include `["github-copilot"]`, team adds `["gis-tools"]`, and project adds `["linter"]`, the effective set is all three.

### MCP Servers

MCP servers also accumulate. Each layer can add servers. Later definitions with the same name override earlier ones.

### Session Config

Session settings (timeout, auto-resume) use last-wins. Project overrides team, team overrides org defaults.

## Decision Tracking

Every configuration value tracks where it came from:

```
plugins:
  - github-copilot    (source: org.defaults)
  - gis-tools         (source: team.urban-planning)
  - project-linter    (source: project)

blocked_items:
  - malicious-plugin  (blocked_by: malicious-*, source: org.security)

denied_additions:
  - some-server       (requested_by: project, reason: team not delegated for MCP)
```

Run `scc config explain` to see this breakdown.

## Examples

### Example 1: Blocked Plugin

Organization config:
```yaml
security:
  blocked_plugins: ["crypto-*"]
```

Team profile:
```yaml
profiles:
  data-team:
    additional_plugins: ["crypto-analyzer"]
```

Result: `crypto-analyzer` is blocked. It matches `crypto-*`. The team cannot use it regardless of delegation.

### Example 2: Missing Delegation

Organization config:
```yaml
delegation:
  teams:
    allow_additional_mcp_servers: ["finance"]
```

Team `platform` tries to add an MCP server in their profile. Result: denied. Only `finance` can add MCP servers.

### Example 3: Project Override Disabled

Team profile:
```yaml
profiles:
  finance:
    delegation:
      allow_project_overrides: false
```

A project in the finance team has `.scc.yaml` with `additional_plugins`. Result: denied. The team doesn't allow project overrides.

### Example 4: Full Chain Success

Organization:
```yaml
defaults:
  allowed_plugins: ["base-plugin"]
delegation:
  teams:
    allow_additional_plugins: ["*"]
```

Team `platform`:
```yaml
additional_plugins: ["team-tool"]
delegation:
  allow_project_overrides: true
```

Project `.scc.yaml`:
```yaml
additional_plugins: ["project-linter"]
```

Result: effective plugins = `["base-plugin", "team-tool", "project-linter"]`. All additions were delegated and nothing was blocked.

### Example 5: Federated Team with Trust Grants

Organization config with federated team:
```yaml
marketplaces:
  shared:
    source: github
    owner: "myorg"
    repo: "shared-plugins"

profiles:
  platform:
    description: "Platform team - config managed externally"
    config_source:
      source: github
      owner: "myorg"
      repo: "platform-config"
      branch: "main"
    trust:
      inherit_org_marketplaces: true
      allow_additional_marketplaces: true
      marketplace_source_patterns:
        - "github.com/myorg/**"
```

External team config (in `platform-config` repo):
```yaml
enabled_plugins:
  - "platform-tools@team-internal"
  - "monitoring@shared"

marketplaces:
  team-internal:
    source: github
    owner: "myorg"
    repo: "platform-internal-plugins"

disabled_plugins:
  - "legacy-tool"  # Disable something from org defaults
```

Result:
- Team can use `shared` marketplace (inherited from org)
- Team can define `team-internal` marketplace (allowed by trust, matches pattern)
- Team can reference plugins from both marketplaces
- Team can disable plugins from org defaults
- Org security rules still apply to all plugins

### Example 6: Federated Team Trust Violation

Organization config:
```yaml
profiles:
  contractor:
    config_source:
      source: url
      url: "https://contractor-configs.example.com/team.json"
    trust:
      inherit_org_marketplaces: true
      allow_additional_marketplaces: true
      marketplace_source_patterns:
        - "github.com/approved-vendors/**"
```

External team config tries to use unauthorized source:
```yaml
marketplaces:
  unauthorized:
    source: github
    owner: "random-org"
    repo: "plugins"
```

Result: **Trust violation error**. The marketplace source `github.com/random-org/plugins` doesn't match the allowed pattern `github.com/approved-vendors/**`.

**Fix**: Either update `marketplace_source_patterns` to allow the source, or use an approved source.

## MCP Server Configuration

Teams and projects can add MCP servers of three types:

### SSE Type (Server-Sent Events)

```yaml
additional_mcp_servers:
  - name: "jira-api"
    type: "sse"
    url: "https://jira.example.com/mcp"
```

### HTTP Type

```yaml
additional_mcp_servers:
  - name: "rest-api"
    type: "http"
    url: "https://api.example.com/mcp"
```

### Stdio Type (Local process)

```yaml
additional_mcp_servers:
  - name: "local-tool"
    type: "stdio"
    command: "/usr/local/bin/mcp-tool"
    args: ["--config", "/etc/tool.conf"]
```

Stdio servers are disabled by default because they run with elevated privileges (mounted workspace, network access, tokens in environment). Organizations must explicitly enable them:

```yaml
security:
  allow_stdio_mcp: true
  allowed_stdio_prefixes:
    - "/usr/local/bin/"
    - "/opt/approved-tools/"
```

If `allow_stdio_mcp` is false (the default), all SCC-managed stdio servers are blocked. When enabled, `allowed_stdio_prefixes` restricts which command paths are permitted. Commands must be absolute paths. Path traversal attempts are blocked via realpath resolution.

If no prefixes are configured, any absolute path is allowed (when stdio is enabled).

This does not apply to stdio MCP servers bundled inside plugins; plugins are allowed or blocked as a whole.

All MCP servers declared in SCC-managed configuration (org/team/project) go through security checks. The server name and URL domain are matched against `blocked_mcp_servers` patterns.

## Exceptions

Sometimes you need to temporarily bypass governance controls. SCC provides a time-bounded exception system with two scopes:

### Local Overrides (Self-Serve)

When delegation denies an addition (team/project not authorized), you can create a local override:

```bash
scc unblock jira-api --ttl 8h --reason "Sprint demo integration"
```

This creates a time-limited exception stored locally. Useful for:
- Urgent integrations during active development
- Testing before requesting permanent delegation
- Personal tooling not worth formal approval

Local overrides **cannot** bypass security blocks (the `blocked_*` patterns). They only work for delegation denials.

### Policy Exceptions (PR-Approved)

When security policies block something, only a policy exception can override it:

```bash
scc exceptions create --policy --id INC-2025-00123 \
  --allow-plugin vendor-tools --ttl 24h \
  --reason "Emergency vendor integration per INC-2025-00123"
```

Policy exceptions:
- Require PR review and approval (stored in config repo)
- Can override any block (security + delegation)
- Should reference an incident/ticket ID
- Have organization-defined TTL limits

### Exception Targets

Both exception types can target:
- **Plugins**: `--allow-plugin <name>`
- **MCP Servers**: `--allow-mcp <name>`
- **Base Images**: `--allow-image <ref>`

### Viewing Active Exceptions

```bash
scc config explain   # Shows active exceptions in output
scc exceptions list  # Lists all exceptions with expiry times
```

### TTL and Expiration

All exceptions are time-bounded:
- Default: 8 hours
- Maximum: 24 hours (configurable by org)
- Formats: `--ttl 8h`, `--expires-at 2025-12-21T17:00:00+01:00`, `--until 17:00`

Expired exceptions are automatically ignored. Run `scc exceptions cleanup` to remove them.

### Exception Stores

| Store | Location | Purpose |
|-------|----------|---------|
| User | `~/.config/scc/exceptions.json` | Personal, machine-local |
| Repo | `.scc/exceptions.json` | Shared with team (if committed) |
| Policy | Config repo | Org-approved, PR-reviewed |

Use `--shared` with `scc unblock` to write to repo store instead of user store.

### Quick Reference

| Scenario | Solution |
|----------|----------|
| Quick status overview | `scc status` |
| Delegation denied, need it now | `scc unblock <target> --ttl 8h --reason "..."` |
| Security blocked, have approval | `scc exceptions create --policy --id INC-... --allow-* ...` |
| Check what's blocked/overridden | `scc config explain` |
| Clean up old exceptions | `scc exceptions cleanup` |

## Debugging Configuration

When something doesn't work as expected:

1. Run `scc status` for a quick overview of your current setup
2. Run `scc config explain` to see effective configuration with sources
3. Check `blocked_items` for security rejections
4. Check `denied_additions` for delegation failures
5. Verify your team is delegated for the resource type
6. Verify your team allows project overrides (if using `.scc.yaml`)
7. Check `Active Exceptions` section for any overrides in effect

## Org Admin Checklist

When setting up organization config:

1. Define security blocks for hard boundaries:
   - `security.blocked_plugins` - plugin name patterns
   - `security.blocked_mcp_servers` - server name/URL patterns
   - `security.blocked_base_images` - Docker image patterns (consider blocking `*:latest`)
2. Configure stdio MCP policy:
   - `security.allow_stdio_mcp` - false by default, enable only if needed
   - `security.allowed_stdio_prefixes` - restrict to trusted paths when enabled
3. Configure plugin governance and defaults:
   - `defaults.allowed_plugins` - whitelist filter (omit for unrestricted, `[]` for deny-all)
   - `defaults.enabled_plugins` - baseline tools everyone gets
4. Configure `delegation.teams` to control which teams can add resources
5. Create team profiles with appropriate `allow_project_overrides` settings
6. Test with `scc config explain` to verify effective configuration

### For Federated Teams

Additional considerations for teams with external config sources:

1. Define `config_source` with appropriate source type (github, git, or url)
2. Configure trust grants carefully:
   - `inherit_org_marketplaces: true` unless team needs complete isolation
   - `allow_additional_marketplaces: false` for maximum control, `true` for team autonomy
   - `marketplace_source_patterns` - use specific patterns, avoid overly permissive wildcards
3. Ensure `defaults.enabled_plugins` doesn't conflict with `inherit_org_marketplaces: false` teams
4. Test federation with `scc team validate` before deployment
5. Use `scc org update --team <name>` to refresh cached configs after team changes
6. Monitor cache staleness - configs older than 7 days require network access
