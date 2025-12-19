# SCC Organization Config Examples

Configuration examples for different security postures and organizational needs.

## Quick Start

Use `quickstart-minimal.json` for a minimal working configuration with secure defaults.

## Examples by Use Case

| File | Use Case | Security Level |
|------|----------|----------------|
| `quickstart-minimal.json` | First-time setup, testing | Secure defaults |
| `org-strict-security.json` | Regulated industries, high-compliance | Locked down |
| `org-teams-delegation.json` | Multi-team organizations | Flexible with controls |
| `org-stdio-hardened.json` | Local MCP tools needed | Hardened stdio |
| `complete-reference.json` | All fields documented | Reference only |

## Schema Version

All examples use schema version 2.0.0 and are validated against `src/scc_cli/schemas/org-v2.schema.json`.

## Key Concepts

**Security Boundaries** - The `security` block defines hard limits that teams cannot override:
- `blocked_plugins`: Plugin patterns always blocked
- `blocked_mcp_servers`: MCP server patterns always blocked
- `blocked_base_images`: Docker image patterns always blocked
- `allow_stdio_mcp`: Whether stdio MCP servers are permitted (default: false)

**Delegation** - The `delegation` block controls what teams can add beyond defaults.

**Profiles** - Each team profile can add plugins and MCP servers within delegation limits.

## Validation

Validate your config:
```bash
scc config explain your-config.json
```
