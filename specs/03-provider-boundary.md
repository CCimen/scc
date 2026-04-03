# Spec 03 — Provider Boundary

## Objective
Move provider-specific behavior into adapters.

## Provider contract
`AgentProvider.prepare_launch(...) -> AgentLaunchSpec`

## Provider responsibilities
- auth resolution
- artifact rendering
- provider launch argv/env/workdir
- provider-core destination set
- native UX integrations such as hooks, rules, plugins, and config files

## Core rules
- Core must not depend on `.claude` or `.codex` layouts directly.
- Provider-native features are not hard enforcement.
- Open Agent Skills are the only intended shared portability surface.
