# S02: CodexAgentRunner, provider-aware image selection, and launch path wiring

**Goal:** Create the Codex runtime artifacts and refactor the launch path to be provider-aware: Dockerfile, image refs, CodexAgentRunner, start_session uses ProviderRuntimeSpec for image/config/volume, OCI runtime receives binary/volume/config from SandboxSpec instead of Claude constants, Claude-only flags gated.
**Demo:** After this: scc start --provider codex builds a Codex-specific SandboxSpec with the right image, settings path, and agent command. The launch reaches Docker exec with codex argv.

## Tasks
