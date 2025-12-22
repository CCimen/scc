# SCC Organization Config Examples

Configuration examples for different security postures and organizational needs. These examples progress from beginner to advanced, helping you understand how to configure SCC for your organization.

## Learning Progression

Follow this order to learn SCC governance incrementally:

| Level | File | What You Learn |
|-------|------|----------------|
| 🟢 Beginner | `01-quickstart-minimal.json` | Basic structure, secure defaults |
| 🟡 Intermediate | `02-org-teams-delegation.json` | Multi-team setup, delegation, tech stack profiles |
| 🔴 Advanced | `03-org-strict-security.json` | Locked-down configs for regulated industries |
| 🔴 Advanced | `04-org-stdio-hardened.json` | Local MCP tools with security controls |
| 📚 Reference | `99-complete-reference.json` | All fields documented (not for production use) |

## Quick Start

Start with `01-quickstart-minimal.json` for a minimal working configuration with secure defaults. Copy and customize for your organization.

## Examples by Use Case

### 01-quickstart-minimal.json - Getting Started
**Best for**: First-time setup, testing, small teams

- Minimal configuration with secure defaults
- Blocks `*:latest` images for reproducibility
- Disables stdio MCP servers (security best practice)
- Single "default" profile for all users

### 02-org-teams-delegation.json - Multi-Team Organizations
**Best for**: Organizations with multiple dev teams using different tech stacks

Demonstrates profiles for common technology archetypes:
- **frontend-react**: Next.js, React, TypeScript teams
- **backend-java**: Spring Boot, Java microservices teams
- **dotnet-sql**: .NET/C# with SQL Server teams
- **python-data**: FastAPI, Python, AI/ML teams
- **platform**: Infrastructure/DevOps teams

Each profile shows:
- Stack-specific MCP server integrations
- Team-specific plugin allowlists
- Appropriate delegation settings

**Map your teams**: Rename profiles to match your team names (e.g., `frontend-react` → `draken-team`).

### 03-org-strict-security.json - High Security
**Best for**: Regulated industries, financial services, healthcare, government

- Empty delegation arrays (no team additions allowed)
- Blocks experimental, beta, and dev tools
- Network policy defaults to `corp-proxy-only`
- Compliance team profile with `isolated` network policy
- 8-hour session timeout with no auto-resume

### 04-org-stdio-hardened.json - Local Tool Access
**Best for**: Teams needing local CLI tools via MCP with security controls

- Enables `allow_stdio_mcp: true` (use with caution)
- Restricts executable paths via `allowed_stdio_prefixes`
- Shows both local-only and hybrid (local + remote) profiles

### 99-complete-reference.json - Documentation Reference
**Best for**: Understanding all available configuration options

- Shows every field with example values
- Demonstrates all three MCP server types (sse, http, stdio)
- **Not intended for production use** - too permissive

## Key Concepts

### Security Boundaries (Org-Level)
The `security` block defines hard limits that **no team can override**:

```json
"security": {
    "blocked_plugins": ["*-experimental"],     // Always blocked
    "blocked_mcp_servers": ["*.untrusted.com"], // Always blocked
    "blocked_base_images": ["*:latest"],        // Always blocked
    "allow_stdio_mcp": false                    // Disable local executables
}
```

### Delegation (What Teams Can Add)
The `delegation` block controls what teams can add **beyond defaults**:

```json
"delegation": {
    "teams": {
        "allow_additional_plugins": ["team-*"],      // Teams can add team-* plugins
        "allow_additional_mcp_servers": ["backend"], // Only backend profile can add servers
        "allow_network_override": ["corp-proxy-only"] // Can switch to proxy mode
    }
}
```

**Key distinction**:
- `security.blocked_*` = Hard blocks, cannot be overridden
- `delegation.allow_*` = Soft limits, can be relaxed via exceptions

### Profiles (Team-Specific Settings)
Each profile defines settings for a specific team or role:

```json
"profiles": {
    "backend-java": {
        "description": "Backend teams using Spring Boot",
        "additional_plugins": ["team-java-tools"],
        "additional_mcp_servers": [...],
        "network_policy": "corp-proxy-only"
    }
}
```

## Technology Stack Mapping

Map the archetype profiles to your organization's teams:

| Archetype | Tech Stack | Example Teams |
|-----------|-----------|---------------|
| `frontend-react` | Next.js, React, TypeScript, Svelte | UI teams, web app teams |
| `backend-java` | Spring Boot, Java, Kotlin | API teams, microservices |
| `dotnet-sql` | .NET Core, C#, SQL Server | Enterprise app teams |
| `python-data` | FastAPI, Python, ML/AI | Data science, ML teams |
| `platform` | Terraform, Kubernetes | DevOps, SRE teams |

## Validation

Validate your config before deploying:

```bash
# Explain config with effective policies
scc config explain your-config.json

# Check doctor output for issues
scc doctor
```

## Schema Version

All examples use schema version 2.0.0 and are validated against `src/scc_cli/schemas/org-v2.schema.json`.

## Next Steps

1. Copy the example closest to your needs
2. Rename to `org-config.json`
3. Customize organization name, id, and contact
4. Adjust security blocks for your policies
5. Create profiles matching your team structure
6. Validate with `scc config explain`
7. Deploy to your config repository
