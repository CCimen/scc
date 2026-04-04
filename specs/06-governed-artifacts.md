# Spec 06 — Governed Artifacts

## Objective
Govern approved skills and provider-native integrations without inventing an SCC-only workflow format.

## Shared portability surface
- open Agent Skills only

## Canonical control-plane model
- `GovernedArtifact` is the approved reusable unit in SCC policy.
- `ArtifactBundle` is the team-facing selection unit. Teams should enable bundles, not raw
  provider plugin references.
- `ProviderArtifactBinding` holds provider-native rendering details only when needed.
- `ArtifactRenderPlan` is the effective per-session/per-provider materialization plan produced
  after org/team/project/user policy merge.

## Artifact kinds
- `skill`
  - open Agent Skills package
  - shared across Claude and Codex whenever possible
- `mcp_server`
  - provider-neutral MCP definition plus transport metadata
  - may be rendered directly or bundled into a native integration package
- `native_integration`
  - provider-specific hooks, rules, local plugin folders, marketplace metadata, app bindings,
    or other native UX glue
- `bundle`
  - named approved grouping of skills, MCP servers, and native integrations
  - the preferred unit for org defaults and team enablement

## Provider surface notes
- Claude:
  - plugin is a self-contained directory that may include skills, agents, hooks, MCP servers,
    LSP config, and plugin-scoped settings
  - marketplace/plugin install surfaces are Claude-native and adapter-owned
  - standalone skills and `CLAUDE.md`-family instructions remain separate native guidance layers
  - Claude plugin capabilities are broader than Codex plugin capabilities; SCC must not treat
    Claude's plugin shape as the generic cross-provider plugin contract
- Codex:
  - plugin is a self-contained directory rooted by `.codex-plugin/plugin.json`
  - Codex plugins bundle skills, apps, and MCP servers; rules and hooks are separate native
    config surfaces, not plugin components
  - `.codex/config.toml` is a native config surface for MCP definitions and plugin state
  - repo and user marketplaces live at `.agents/plugins/marketplace.json`
  - standalone skills live under `.agents/skills`
  - rules live under `.codex/rules/*.rules`
  - hooks live in `.codex/hooks.json`
  - `AGENTS.md` is a separate instruction-discovery layer, not a plugin component
  - Codex rules and hooks are native guardrail and UX surfaces; they are not the hard
    enforcement boundary and should not be represented as if they were portable plugin content

## Plugin semantics
- A plugin is a distribution unit, not the canonical SCC policy object.
- SCC should not force teams to author separate "Claude plugin config" and "Codex plugin config"
  for the same workflow.
- Teams should select approved bundles once. Adapters may then materialize that bundle as:
  - a Claude marketplace/plugin + hook configuration
  - a Codex local plugin with `.codex-plugin/plugin.json`
  - repo-local or user-local marketplace entries
  - shared skill and MCP installation surfaces
- Bundles must remain audit-friendly. Their constituent skills, MCP servers, and native
  integrations should stay individually visible for approval, provenance, and diagnostics.

## Experience requirements
- Organization experience:
  - curate one approved artifact catalog and one approved bundle catalog
  - delegate what teams may enable without asking org admins to hand-author provider-native files
  - review provenance, pinning, publisher metadata, and install intent in one place
- Team experience:
  - choose approved bundles, not raw Claude marketplace entries or raw Codex plugin folders
  - avoid dual maintenance of a "Claude team config" and a "Codex team config"
  - be able to see which bundle members are shared across providers and which members are
    provider-native bindings
- Developer experience:
  - switch between Claude and Codex with the same active org/team policy
  - receive the closest truthful native projection for the chosen provider
  - understand what SCC rendered, where it rendered it, and what was skipped

## Rendering semantics
- Core computes one `ArtifactRenderPlan` from org/team/project/user policy.
- The selected provider adapter owns projection from that plan into provider-native files,
  directories, and install surfaces.
- Projection must be deterministic and idempotent for a given effective plan, provider, and
  workspace scope.
- Functional parity means the same approved SCC bundle produces the closest safe native outcome
  on both providers. It does not require identical on-disk plugin structures.
- A single bundle may render as:
  - one provider-native plugin package
  - multiple standalone native files
  - a mix of plugin package plus adjacent native config surfaces
- Claude projection may emit a plugin containing skills, agents, hooks, MCP, and LSP, or may
  emit standalone native surfaces when that produces a simpler or more truthful result.
- Codex projection may emit a `.codex-plugin` bundle for skills, apps, and MCP, while also
  emitting separate `.codex/hooks.json`, `.codex/rules/*.rules`, `.codex/config.toml`, and
  `AGENTS.md` outputs. SCC must not try to force those Codex-native surfaces into the plugin
  directory just to mimic Claude.

## Recommended packaging model
- Preferred source of truth:
  - one org-approved artifact repository or registry
  - one canonical SCC bundle definition per team pack or shared capability pack
  - bundle contents may include shared skills, shared MCP definitions, and provider-native
    bindings in the same source tree
- Preferred team policy shape:
  - team config references approved bundle IDs, not raw provider marketplace URLs
  - org config maps those bundle IDs to approved source refs and pinning policy
  - developers should not need to know whether the chosen provider ultimately consumes a plugin,
    a marketplace entry, a rules file, or a hook file
- Optional distribution layer:
  - CI may publish generated Claude or Codex marketplace artifacts for direct native use
  - those published artifacts are build outputs, not the canonical SCC authoring model
- Product language may call this a "team pack" or "team plugin" for simplicity, but the
  implementation should keep the provider-neutral bundle model underneath

## Guidance and merge strategy
- Prefer skills for reusable team workflows and instruction sets.
- Reserve `AGENTS.md`, `CLAUDE.md`, rules, and hooks for:
  - always-on policy
  - native guardrails
  - native UX affordances that cannot be expressed cleanly as a skill
- SCC should avoid overwriting developer-authored instruction or config files blindly.
- Where the native surface supports composition, SCC should use separate managed files.
- Where the native surface requires one canonical file, SCC should:
  - merge deterministically
  - preserve non-SCC content when safe
  - mark SCC-managed sections or files clearly
  - fail clearly instead of silently discarding user content
- In practice this means:
  - Codex rules are a good fit for separate SCC-managed files under `.codex/rules/`
  - Codex hooks, Codex `config.toml`, and similar single-file surfaces need explicit merge
    strategy
  - `AGENTS.md` and `CLAUDE.md` should be used sparingly because they are high-precedence
    guidance layers that may already be owned by the repo
- If a bundle's guidance can be expressed as open Agent Skills, prefer that path over native
  instruction-file rendering because it is more portable and less collision-prone

## Governance model
- Org owns:
  - approved artifact catalog
  - approved bundle catalog
  - approved public/private sources
  - provenance, pinning, install intent defaults, and allowlist approval
  - delegation rules for what teams may enable or add
- Team owns:
  - bundle selection within org-delegated bounds
  - optional team-local narrowing or additional approved bundles
- Project and user own:
  - narrowing only
  - local disablement, stricter defaults, or local opt-out
  - request metadata for widening, but not effective widening in v1
- Each workspace/session runs under one active team context. SCC must not implicitly union
  multiple team artifact sets in one session.

## Installation intent
- Canonical install intent should be provider-neutral and explain operator expectations.
- Recommended SCC intent values:
  - `required` — render/install automatically for the selected provider
  - `available` — expose for opt-in or browsing, not auto-enabled
  - `disabled` — explicitly not allowed in the effective session
  - `request-only` — visible as an approved request target, not effective until promoted
- Adapters may translate this into provider-native policy fields such as marketplace
  installation flags or per-plugin enabled/disabled state.

## Adapter-owned native integrations
- Claude renderer:
  - `.claude` config and hook wiring
  - Claude-native marketplace/plugin metadata and local marketplace materialization
  - plugin-scoped assets such as agents or LSP config when a bundle calls for them
  - optional provider-native skill placement when needed
  - optional rendering of managed instruction content into Claude-native guidance surfaces
- Codex renderer:
  - `.codex` config
  - `.codex/rules/*.rules`
  - `.codex/hooks.json`
  - local plugin folders containing `.codex-plugin/plugin.json`
  - optional `.mcp.json` and `.app.json`
  - repo or user marketplace catalogs at `.agents/plugins/marketplace.json`
  - Codex-native plugin enable/disable metadata
  - optional rendering of managed instruction content into `AGENTS.md` or adjacent Codex-facing
    instruction layers
- Native integrations must remain adapter-owned. Core policy should never depend on
  `enabledPlugins`, `extraKnownMarketplaces`, or Codex marketplace JSON as canonical inputs.

## Portability rules
- Skills are the primary cross-provider portability layer.
- MCP definitions should stay provider-neutral unless a provider-native binding is genuinely
  required for packaging or UX.
- Provider-native hooks, rules, plugin manifests, and marketplace metadata are not portable and
  must be rendered from the same governed artifact plan rather than authored separately per team.
- Persistent instruction layers such as `AGENTS.md`, `CLAUDE.md`, Codex rules, or provider hook
  configs are native bindings. They may be derived from the same approved SCC bundle, but SCC
  should not pretend they are interchangeable file formats.
- Claude plugin capability and Codex plugin capability are intentionally asymmetric. SCC should
  preserve that asymmetry in adapter renderers instead of flattening both into one fake plugin
  abstraction.
- When one provider lacks a native feature, SCC should still apply the shared parts of the plan
  and report skipped native bindings truthfully in diagnostics.

## Sources and pinning
- Artifact sources may be public or private repos, directories, or approved remote manifests.
- Every governed artifact and bundle should carry:
  - source reference
  - revision/ref or version pin
  - approval status
  - owner or publisher metadata
  - audit-friendly identifier
- Team configs should reference approved artifact or bundle IDs, not raw URLs whenever possible.

## Diagnostics and truthfulness
- SCC must show:
  - active team context
  - selected provider
  - effective bundles and artifacts
  - which parts are shared vs provider-native
  - which bindings were rendered, skipped, or blocked
  - which files or install surfaces were written for the current provider
  - whether native files were rendered as standalone managed files, merged into an existing file,
    or skipped to avoid conflict
  - why a requested artifact was unavailable
- SCC must not claim Codex plugin parity until a real Codex renderer and installation path exist.
- Switching providers should re-render from the same effective artifact plan; it should not
  require a second team policy file.

## Example
```yaml
governed_artifacts:
  artifacts:
    code-review-skill:
      kind: skill
      source:
        type: git
        url: https://git.example.se/ai/agent-artifacts.git
        path: skills/code-review
        ref: v1.4.2
      install_intent: available
    github-mcp:
      kind: mcp_server
      source:
        type: git
        url: https://git.example.se/ai/agent-artifacts.git
        path: mcp/github.json
        ref: v1.4.2
      install_intent: required
    github-native:
      kind: native_integration
      install_intent: available
      bindings:
        claude:
          hooks: ./claude/github-hooks.json
          marketplace_bundle: ./claude/github-marketplace
        codex:
          plugin_bundle: ./codex/github-plugin
          rules: ./codex/rules/github.rules
    team-guidance:
      kind: native_integration
      install_intent: required
      bindings:
        claude:
          instructions: ./claude/CLAUDE.team.md
        codex:
          instructions: ./codex/AGENTS.team.md
  bundles:
    github-dev:
      members:
        - code-review-skill
        - github-mcp
        - github-native
        - team-guidance
      install_intent: available
profiles:
  ai-team:
    enabled_bundles:
      - github-dev
```

In this model the team selects `github-dev` once. SCC then renders the shared skill and MCP
everywhere it can, renders Codex rules/hooks/plugin metadata only for Codex sessions, renders
Claude-native marketplace/hooks only for Claude sessions, and can project approved team guidance
into provider-native instruction files without forcing two separate team policy documents.

## Governance requirements
- provenance
- pinning
- installation intent
- allowlist approval
- auditability
