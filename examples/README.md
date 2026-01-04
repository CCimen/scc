# SCC Organization Config Examples

Ready-to-use configuration templates for SCC (Sandboxed Code CLI). Pick a path and copy a file—no need to read everything.

## Contents

- [Pick Your Path](#pick-your-path)
- [Quick Start](#quick-start)
- [Example Index](#example-index)
- [Real-world References](#real-world-references)
- [Skeleton Templates](#skeleton-templates)
- [Validation](#validation)
- [Key Concepts](#key-concepts)
- [Schema Information](#schema-information)
- [Setup Checklist](#setup-checklist)

---

## Pick Your Path

- **Teams own their marketplaces/plugins (federated, team-owned)** → **Example Org**:
  - [10-example-org-federated.json](10-example-org-federated.json)
  - Matching team configs:
    - [10-example-org-frontend-team-config.json](10-example-org-frontend-team-config.json)
    - [10-example-org-backend-team-config.json](10-example-org-backend-team-config.json)
    - [10-example-org-ml-team-config.json](10-example-org-ml-team-config.json)
- **Org controls marketplaces (centralized)**:
  - Small org or single team → [01-quickstart-minimal.json](01-quickstart-minimal.json)
  - Multiple teams → [02-org-teams-delegation.json](02-org-teams-delegation.json)
- **Strict security / compliance baseline** → [03-org-strict-security.json](03-org-strict-security.json)
  - If you need local MCP tools, also review [04-org-stdio-hardened.json](04-org-stdio-hardened.json)

<details>
<summary>More options</summary>

- **Hybrid GitLab + GitHub sources** → [07-hybrid-gitlab-github-skeleton.json](07-hybrid-gitlab-github-skeleton.json)
- **Federation reference (all source types)** → [05-org-federated-teams.json](05-org-federated-teams.json)
- **Need a complete reference** → [99-complete-reference.json](99-complete-reference.json)

</details>

---

## Quick Start

### Federated: teams own marketplaces (Example Org path)

```bash
# 1) Copy org config
cp examples/10-example-org-federated.json org-config.json

# 2) Edit org fields + repo names
# - organization.name / id / contact
# - team config repo names in profiles.*.config_source

# 3) Validate org config
scc org validate org-config.json
```

This pattern assumes each team owns its own `marketplaces` in the team config.

Team configs live in **separate GitHub repos**. Use these as templates:

- `examples/10-example-org-frontend-team-config.json`
- `examples/10-example-org-backend-team-config.json`
- `examples/10-example-org-ml-team-config.json`

### Centralized: org controls marketplaces

```bash
# Small org or single team
cp examples/01-quickstart-minimal.json org-config.json

# Multi-team org
# cp examples/02-org-teams-delegation.json org-config.json

# Validate org config
scc org validate org-config.json
```

If you plan to federate team configs but keep org-level marketplaces, start from:

```
examples/06-github-federated-skeleton.json
```

---

## Example Index

| Example | Intent | Best for | Tags |
|---------|--------|----------|------|
| [01-quickstart-minimal.json](01-quickstart-minimal.json) | Centralized | Small org, single team | beginner, minimal |
| [02-org-teams-delegation.json](02-org-teams-delegation.json) | Centralized | Multi-team org | delegation |
| [03-org-strict-security.json](03-org-strict-security.json) | Centralized | Regulated/security-first | security |
| [04-org-stdio-hardened.json](04-org-stdio-hardened.json) | Centralized | Local MCP tools with guardrails | mcp, security |
| [05-org-federated-teams.json](05-org-federated-teams.json) | Federated | Full federation reference | advanced |
| [06-github-federated-skeleton.json](06-github-federated-skeleton.json) | Federated | GitHub-only template | skeleton |
| [07-hybrid-gitlab-github-skeleton.json](07-hybrid-gitlab-github-skeleton.json) | Federated | GitLab configs + GitHub plugins | hybrid |
| [08-sundsvall-kommun-org.json](08-sundsvall-kommun-org.json) | Mixed | Org marketplace + one federated team | real-world |
| [08-sundsvall-ai-team-config.json](08-sundsvall-ai-team-config.json) | Federated | Team config example | real-world |
| [09-org-safety-net-enabled.json](09-org-safety-net-enabled.json) | Centralized | Safety-net plugin example | plugin |
| [10-example-org-federated.json](10-example-org-federated.json) | Federated | Team-owned marketplaces | real-world |
| [10-example-org-frontend-team-config.json](10-example-org-frontend-team-config.json) | Federated | Frontend team config | real-world |
| [10-example-org-backend-team-config.json](10-example-org-backend-team-config.json) | Federated | Backend team config | real-world |
| [10-example-org-ml-team-config.json](10-example-org-ml-team-config.json) | Federated | ML team config | real-world |
| [99-complete-reference.json](99-complete-reference.json) | Reference | All fields documented | reference |
| [team-config-example.json](team-config-example.json) | Reference | Team config schema example | reference |

---

## Advanced & Reference (collapsed)

<details>
<summary>Security, MCP, federation, hybrid, full reference</summary>

- Strict security baseline: [03-org-strict-security.json](03-org-strict-security.json)
- Local MCP with guardrails: [04-org-stdio-hardened.json](04-org-stdio-hardened.json)
- Full federation reference: [05-org-federated-teams.json](05-org-federated-teams.json)
- Hybrid GitLab + GitHub: [07-hybrid-gitlab-github-skeleton.json](07-hybrid-gitlab-github-skeleton.json)
- Safety-net plugin example: [09-org-safety-net-enabled.json](09-org-safety-net-enabled.json)
- Complete reference: [99-complete-reference.json](99-complete-reference.json)

</details>

## Real-world References

### Example Org (Team-owned marketplaces)

**Use this when** teams maintain their own plugins/marketplaces and the org file should stay minimal.

- Org config: [10-example-org-federated.json](10-example-org-federated.json)
- Team configs:
  - [10-example-org-frontend-team-config.json](10-example-org-frontend-team-config.json)
  - [10-example-org-backend-team-config.json](10-example-org-backend-team-config.json)
  - [10-example-org-ml-team-config.json](10-example-org-ml-team-config.json)

**Key design decisions:**

1. **No org marketplaces** — each team defines its own marketplace
2. **All teams are federated** — org config only references team repos
3. **Trust grants allow team marketplaces** — `allow_additional_marketplaces: true`

**Pick Example Org if** you want minimal org ownership and maximum team autonomy.

### Sundsvalls kommun (Org marketplace + selective federation)

**Use this when** the org wants a shared marketplace, but some teams need their own configs.

- Org config: [08-sundsvall-kommun-org.json](08-sundsvall-kommun-org.json)
- AI team config: [08-sundsvall-ai-team-config.json](08-sundsvall-ai-team-config.json)

**Pick Sundsvall if** you want a fuller, org-led reference with a mixed model.

---

## Skeleton Templates

<details>
<summary>06-github-federated-skeleton.json (GitHub-only)</summary>

**Best for**: All sources hosted in GitHub.

**Customize**:
1. Replace `your-org` with your GitHub organization name
2. Create the team config repos on GitHub
3. Adjust trust grants per team

</details>

<details>
<summary>07-hybrid-gitlab-github-skeleton.json (GitLab configs + GitHub plugins)</summary>

**Best for**: Private GitLab for team configs, public GitHub for plugins.

**Customize**:
1. Replace `gitlab.your-company.com` with your GitLab domain
2. Replace `your-company` with your GitHub organization
3. Adjust `marketplace_source_patterns` to match your repos

</details>

---

## Validation

```bash
# Org config file validation
scc org validate org-config.json

# Effective config (uses installed org config; no file argument)
scc config explain

# Health checks
scc doctor
scc status
```

**Team config validation**

After the org config is installed, validate a team by name:

```
scc team validate <TEAM_NAME>
```

If you are unsure which commands your version supports, see:

- [docs/CLI-REFERENCE.md](../docs/CLI-REFERENCE.md)

---

## Key Concepts

**Security boundaries** are hard blocks. Teams cannot override `security.*`.

**Delegation** controls what teams can add (plugins, MCP servers, network overrides).

**Federation** means team configs live in external repos (`profiles.*.config_source`).

**Trust grants** gate team-owned marketplaces. If teams define `marketplaces` in their team config,
set `allow_additional_marketplaces: true` and restrict `marketplace_source_patterns`.

---

## Schema Information

All org examples use:
- **Schema Version**: `1.0.0`
- **Schema File**: `src/scc_cli/schemas/org-v1.schema.json`

Team config examples use:
- **Team Config Schema**: `src/scc_cli/schemas/team-config.v1.schema.json`

---

## Setup Checklist

1. [ ] Pick a path from **Pick Your Path**
2. [ ] Copy the matching example
3. [ ] Replace organization name, id, and contact
4. [ ] Update team config repo URLs (if federated)
5. [ ] Validate with `scc org validate org-config.json`
6. [ ] (Optional) Run `scc config explain` after installing the org config
7. [ ] Host the org config and share the URL with your team

---

## Marketplace Plugins

If you plan to enable marketplace plugins (like safety-net), see:

- [docs/MARKETPLACE.md](../docs/MARKETPLACE.md)
