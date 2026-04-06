# Spec 03 — Provider Boundary

## Objective
Move provider-specific behavior into adapters.

## Provider contract
`AgentProvider.prepare_launch(...) -> AgentLaunchSpec`

## Provider responsibilities
- auth resolution
- rendering governed artifacts into provider-native files and install surfaces
- provider launch argv/env/workdir
- provider-core destination set
- native UX integrations such as hooks, rules, plugins, AGENTS/CLAUDE guidance files, and config files

## Core rules
- Core must not depend on `.claude` or `.codex` layouts directly.
- Provider-native features are not hard enforcement.
- Open Agent Skills are the only intended shared portability surface.
- One org/team/project/user policy should drive both providers; adapters are responsible for
  translating the same effective artifact plan into Claude- or Codex-native layouts.
- Provider-native component shapes are asymmetric. Claude plugins may carry hooks, agents, and
  LSP, while Codex plugins bundle skills, apps, and MCP and rely on separate rules, hooks,
  config, and `AGENTS.md` layers. Core must not flatten those differences into one generic
  plugin contract.
- Provider capability profiles must stay truthful about what is actually implemented for that
  provider, including skills support, resume support, and native integrations.
- Claude owns `.claude` config, `CLAUDE.md`-adjacent native guidance, hook wiring, and any
  Claude marketplace/plugin assets.
- Codex owns `.codex` config, `.codex/rules/*.rules`, `.codex/hooks.json`, `AGENTS.md`-adjacent
  native guidance, `.codex-plugin/plugin.json`, local plugin bundles, and repo or user
  marketplace entries under `.agents/plugins/marketplace.json`.
- Codex rules and hooks are adapter-owned native guardrails and UX surfaces, not the hard
  enforcement boundary. SCC-owned runtime wrappers and topology remain the hard control.
