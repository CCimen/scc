# SCC Organization Config Examples

Ready-to-use configuration templates for SCC (Sandboxed Code CLI). Copy the example that best matches your needs and customize it.

---

## Quick Start

**New to SCC?** Start here:

```bash
# 1. Copy a skeleton template
cp examples/06-github-federated-skeleton.json org-config.json

# 2. Edit with your organization details
# - Change "your-org" to your GitHub organization
# - Update organization name, id, and contact

# 3. Validate
scc config explain org-config.json
```

---

## Which Example Should I Use?

| Your Situation | Use This | Why |
|----------------|----------|-----|
| First time setting up SCC | `01-quickstart-minimal.json` | Minimal, secure defaults |
| Multiple teams, same org | `02-org-teams-delegation.json` | Team profiles with delegation |
| Regulated industry (finance, healthcare) | `03-org-strict-security.json` | Maximum security controls |
| Need local CLI tools via MCP | `04-org-stdio-hardened.json` | Secure stdio configuration |
| Teams manage their own configs | `06-github-federated-skeleton.json` | GitHub-only federation |
| Private GitLab + public GitHub plugins | `07-hybrid-gitlab-github-skeleton.json` | Mixed source federation |
| **Swedish municipality / public sector** | `08-sundsvall-kommun-org.json` | Real-world reference config |
| **Federated teams, no org marketplaces** | `10-gavle-kommun-federated.json` | Minimal team-owned marketplaces |
| **Protect git history with safety-net** | `09-org-safety-net-enabled.json` | Marketplace plugin with git protection |
| See all available options | `99-complete-reference.json` | Reference only (not for production) |

---

## Learning Progression

Build your understanding step by step:

| Level | File | What You Learn |
|-------|------|----------------|
| 🟢 Beginner | `01-quickstart-minimal.json` | Basic structure, secure defaults |
| 🟡 Intermediate | `02-org-teams-delegation.json` | Multi-team setup, delegation, profiles |
| 🔴 Advanced | `03-org-strict-security.json` | Locked-down configs for compliance |
| 🔴 Advanced | `04-org-stdio-hardened.json` | Local MCP tools with security |
| 🔴 Advanced | `05-org-federated-teams.json` | Complete federated example |
| 🟣 Skeleton | `06-github-federated-skeleton.json` | GitHub-only federation template |
| 🟣 Skeleton | `07-hybrid-gitlab-github-skeleton.json` | GitLab + GitHub hybrid template |
| 🏛️ Real-World | `08-sundsvall-kommun-org.json` | Swedish municipality with real teams |
| 🏛️ Real-World | `08-sundsvall-ai-team-config.json` | AI team's federated config |
| 🏛️ Real-World | `10-gavle-kommun-federated.json` | Minimal federation with team-owned marketplaces |
| 🏛️ Real-World | `10-gavle-frontend-team-config.json` | Frontend team config example |
| 🏛️ Real-World | `10-gavle-backend-team-config.json` | Backend team config example |
| 🏛️ Real-World | `10-gavle-ml-team-config.json` | ML team config example |
| 🔒 Plugin | `09-org-safety-net-enabled.json` | Marketplace plugin with git protection |
| 📚 Reference | `99-complete-reference.json` | All fields documented |
| 📚 Reference | `team-config-example.json` | External team config format |

---

## Skeleton Templates (Copy These)

### 06-github-federated-skeleton.json
**Best for**: Organizations using GitHub for everything

```
Your Org (GitHub)
├── org-config repo (this file)
├── shared-plugins repo (marketplace)
├── platform-team-config repo (federated team config)
└── backend-team-config repo (federated team config)
```

**Features**:
- All sources are GitHub repos
- Platform team can define additional marketplaces
- Backend team inherits org marketplaces only
- Frontend team uses inline config (no federation)

**Customize**:
1. Replace `your-org` with your GitHub organization name
2. Create the team config repos on GitHub
3. Adjust trust grants per team's needs

### 07-hybrid-gitlab-github-skeleton.json
**Best for**: Organizations with private GitLab for configs, public GitHub for plugins

```
Your Org
├── GitLab (private) → team configs
│   ├── teams/platform-config.git (SSH clone)
│   └── teams/backend-config.git (HTTPS)
└── GitHub (public) → plugins/marketplaces
    └── your-company/public-plugins
```

**Features**:
- Team configs stored on private GitLab (SSH or HTTPS)
- Shared plugins on public GitHub
- Contractors limited to GitHub public only
- Security team uses inline config (maximum control)

**Customize**:
1. Replace `gitlab.your-company.com` with your GitLab domain
2. Replace `your-company` with your GitHub organization
3. Adjust `marketplace_source_patterns` to match your repos

---

## Real-World Reference: Sundsvalls kommun

### 08-sundsvall-kommun-org.json
**Best for**: Swedish municipalities, public sector organizations, or anyone wanting a complete real-world example

This is a production-ready configuration based on actual team structures:

```
Sundsvalls kommun (GitHub: sundsvalls-kommun)
├── scc-org-config           ← This config file
├── scc-shared-plugins       ← Shared marketplace
└── ai-team-scc-config       ← AI team's federated config
```

**Teams:**

| Team | Tech Stack | Federation | Why |
|------|------------|------------|-----|
| **Dept44** | Spring Boot, Java, WSO2 | Inline | Core infrastructure, needs org control |
| **Draken** | React, Next.js, TypeScript | Inline | Ärendehantering (case management) |
| **Hydran** | React, Next.js, TypeScript | Inline | Verksamhetssystem |
| **AI-team** | Python FastAPI, SvelteKit | Federated | LLM/inference work, needs rapid iteration |

**Key design decisions:**

1. **Dept44 is NOT federated** - Backend/API infrastructure teams need tight governance
2. **AI-team IS federated** - They iterate fast on tooling for LLM inference work
3. **Draken & Hydran allow project overrides** - Frontend teams can customize per-project
4. **Only Dept44 and AI-team can add MCP servers** - Infrastructure teams have those needs
5. **90-day stats retention** - Public sector may need audit trails

**GitHub structure to replicate:**
```bash
# Create the organization repos
gh repo create sundsvalls-kommun/scc-org-config --public
gh repo create sundsvalls-kommun/scc-shared-plugins --public
gh repo create sundsvalls-kommun/ai-team-scc-config --public
gh repo create sundsvalls-kommun/ai-team-plugins --public
```

### 08-sundsvall-ai-team-config.json
**Best for**: Understanding what the AI team stores in their federated config

This file would be in the `ai-team-scc-config` repo:
- Enables Python/FastAPI/Svelte plugins from shared marketplace
- Defines their own `ai-tools` marketplace for LLM-specific plugins
- Disables Java plugins (not relevant for their stack)

**Customize for your AI team:**
- Add prompt engineering and LLM integration plugins
- Reference your inference tooling helpers
- Disable plugins your team doesn't need

---

## Real-World Reference: Gävle kommun (Federated Teams)

### 10-gavle-kommun-federated.json
**Best for**: Teams that manage their own plugins and marketplaces in GitHub

This config keeps the org file minimal and delegates plugins/marketplaces to team repos:

```
Gävle kommun (GitHub: gavle-kommun)
├── scc-org-config                  ← org config (this file)
├── scc-frontend-team-config        ← team config (frontend)
├── scc-backend-team-config         ← team config (backend)
└── scc-ml-team-config              ← team config (ML)

Team marketplaces (per team)
├── gavle-frontend-plugins
├── gavle-backend-plugins
└── gavle-ml-plugins
```

**Teams:**

| Team | Stack | Config Source |
|------|-------|---------------|
| **frontend** | React / TypeScript | `scc-frontend-team-config` |
| **backend** | Java / Spring Boot | `scc-backend-team-config` |
| **ml** | Python / ML backend | `scc-ml-team-config` |

**Key design decisions:**

1. **No org marketplaces** - each team defines its own marketplace
2. **Team configs live in GitHub** - org config only references repos
3. **Trust grants allow team marketplaces** - `allow_additional_marketplaces: true`

### Team config examples

- `10-gavle-frontend-team-config.json`
- `10-gavle-backend-team-config.json`
- `10-gavle-ml-team-config.json`

---

## Example Details

### 01-quickstart-minimal.json
**Best for**: First-time setup, testing, small teams

- Minimal configuration with secure defaults
- Blocks `*:latest` images for reproducibility
- Disables stdio MCP servers (security best practice)
- Single "default" profile for all users

### 02-org-teams-delegation.json
**Best for**: Organizations with multiple dev teams

Profiles for common technology stacks:
- **frontend-react**: Next.js, React, TypeScript
- **backend-java**: Spring Boot, Java, Kotlin
- **dotnet-sql**: .NET Core, C#, SQL Server
- **python-data**: FastAPI, Python, ML/AI
- **platform**: Terraform, Kubernetes, DevOps

### 03-org-strict-security.json
**Best for**: Regulated industries (finance, healthcare, government)

- Empty delegation arrays (no team additions allowed)
- Blocks experimental, beta, and dev tools
- Network policy defaults to `corp-proxy-only`
- 8-hour session timeout, no auto-resume

### 04-org-stdio-hardened.json
**Best for**: Teams needing local CLI tools via MCP

- Enables `allow_stdio_mcp: true` (use with caution)
- Restricts executable paths via `allowed_stdio_prefixes`
- Shows both local-only and hybrid profiles

### 05-org-federated-teams.json
**Best for**: Reference for all federation patterns

Comprehensive example showing:
- GitHub source (`source: "github"`)
- Git source (`source: "git"` for GitLab SSH)
- URL source (`source: "url"` for HTTPS endpoints)
- Various trust grant configurations

### 09-org-safety-net-enabled.json
**Best for**: Teams wanting to protect git history from accidental destructive commands

Demonstrates the [scc-safety-net](https://github.com/CCimen/sandboxed-code-plugins/tree/main/scc-safety-net) marketplace plugin:
- Enables the official marketplace (`sandboxed-code-official`)
- Enables `scc-safety-net` plugin for all teams
- Configures `security.safety_net` policy settings
- Blocks force pushes, hard resets, and other destructive git commands

See [docs/MARKETPLACE.md](../docs/MARKETPLACE.md) for full plugin documentation.

---

## Key Concepts

### Security Boundaries (Cannot Be Overridden)

```json
"security": {
    "blocked_plugins": ["*-experimental"],
    "blocked_mcp_servers": ["*.untrusted.com"],
    "blocked_base_images": ["*:latest"],
    "allow_stdio_mcp": false
}
```

These are **hard blocks**. No team or project can bypass them.

### Delegation (What Teams Can Add)

```json
"delegation": {
    "teams": {
        "allow_additional_plugins": ["*"],
        "allow_additional_mcp_servers": ["platform", "backend"]
    }
}
```

- `["*"]` = any team can add
- `["platform", "backend"]` = only these teams can add

### Federated Team Config

Teams can manage their own plugins in external repositories:

**Org config** (defines where team config lives):
```json
"profiles": {
    "platform": {
        "config_source": {
            "source": "github",
            "owner": "your-org",
            "repo": "platform-team-config"
        },
        "trust": {
            "inherit_org_marketplaces": true,
            "allow_additional_marketplaces": true,
            "marketplace_source_patterns": ["github.com/your-org/**"]
        }
    }
}
```

**Team config** (stored in external repo):
```json
{
    "schema_version": 1,
    "enabled_plugins": ["my-tool@team-marketplace"],
    "disabled_plugins": ["legacy-tool"],
    "marketplaces": {
        "team-marketplace": {
            "source": "github",
            "owner": "your-org",
            "repo": "team-plugins"
        }
    }
}
```

### Trust Grants Explained

| Setting | Default | Effect |
|---------|---------|--------|
| `inherit_org_marketplaces` | `true` | Team can use org-defined marketplaces |
| `allow_additional_marketplaces` | `false` | When true, team can define their own marketplaces |
| `marketplace_source_patterns` | `[]` | URL patterns for allowed marketplace sources |

**Note:** If teams maintain their own marketplaces, set `allow_additional_marketplaces: true`.
When `false`, any `marketplaces` block in the team config will fail trust validation.

---

## Validation Commands

```bash
# Validate org config structure and semantics
scc org validate org-config.json

# Show effective policies (useful for debugging)
scc config explain org-config.json

# Check system health and prerequisites
scc doctor

# Show current team and config status
scc status
```

**Team config validation** (schema check):

```bash
uv run python - <<'PY'
import json
from pathlib import Path
from jsonschema import Draft7Validator

schema = json.loads(Path("src/scc_cli/schemas/team-config.v1.schema.json").read_text())
validator = Draft7Validator(schema)

for path in sorted(Path("examples").glob("*team-config*.json")):
    data = json.loads(path.read_text())
    errors = list(validator.iter_errors(data))
    print(path, "OK" if not errors else "INVALID")
PY
```

---

## Schema Information

All examples use:
- **Schema Version**: `1.0.0`
- **Schema File**: `src/scc_cli/schemas/org-v1.schema.json`
- **Team Config Schema**: `src/scc_cli/schemas/team-config.v1.schema.json`

---

## Setup Checklist

1. [ ] Copy the skeleton that matches your setup
2. [ ] Update organization name, id, and contact
3. [ ] Replace placeholder org/repo names with real values
4. [ ] Define security blocks for your policies
5. [ ] Create team profiles for your organization
6. [ ] Set up external repos for federated teams (if applicable)
7. [ ] Validate with `scc config explain`
8. [ ] Host config and share URL with your team
