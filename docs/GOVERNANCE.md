# Governance Model

SCC enforces a 3-layer configuration system. Organizations define security boundaries. Teams add tools within those boundaries. Projects customize further if their team allows it.

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

Organizations define patterns that block plugins or MCP servers globally:

```yaml
security:
  blocked_plugins:
    - "malicious-*"
    - "untrusted-tool"
  blocked_mcp_servers:
    - "*.untrusted.com"
    - "insecure-api"
```

These use glob patterns (fnmatch). If a plugin matches `malicious-*`, no team or project can use it. This is absolute.

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

All types go through security checks. The server name and URL domain are matched against `blocked_mcp_servers` patterns.

## Debugging Configuration

When something doesn't work as expected:

1. Run `scc config explain` to see effective configuration with sources
2. Check `blocked_items` for security rejections
3. Check `denied_additions` for delegation failures
4. Verify your team is delegated for the resource type
5. Verify your team allows project overrides (if using `.scc.yaml`)

## Org Admin Checklist

When setting up organization config:

1. Define `security.blocked_plugins` and `security.blocked_mcp_servers` for hard boundaries
2. Set `defaults.allowed_plugins` for baseline tools everyone gets
3. Configure `delegation.teams` to control which teams can add resources
4. Create team profiles with appropriate `allow_project_overrides` settings
5. Test with `scc config explain` to verify effective configuration
