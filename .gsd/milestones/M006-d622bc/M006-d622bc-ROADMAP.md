# M006-d622bc: Provider Selection UX and End-to-End Codex Launch

## Vision
SCC becomes a genuine multi-provider runtime. Users choose between Claude and Codex via config or CLI flag, validated against org/team policy. Provider resolution is request-scoped, not a bootstrap-global default. Provider identity is part of container naming, volume naming, session identity, and resume identity — Claude and Codex coexist on the same workspace without collision. The entire launch flow, TUI, doctor readiness, Quick Resume, machine-readable outputs, and diagnostics adapt to the selected provider. Codex has its own Dockerfile, runner, image ref, and operator-ready image lifecycle with standardized build commands. Claude-only features are gated, not renamed. Pre-M006 configs and sessions migrate transparently.

## Slice Overview
| ID | Slice | Risk | Depends | Done | After this |
|----|-------|------|---------|------|------------|
| S01 | Provider selection config, CLI flag, and bootstrap dispatch | medium | — | ✅ | scc provider show prints the active provider. scc provider set codex persists it. scc start --provider codex overrides the default. Bootstrap dispatches the correct agent_provider, agent_runner, and safety_adapter based on the resolved provider. |
| S02 | CodexAgentRunner, provider-aware image selection, and launch path wiring | high | S01 | ✅ | scc start --provider codex builds a Codex-specific SandboxSpec with the right image, settings path, and agent command. The launch reaches Docker exec with codex argv. |
| S03 | Provider-aware branding, panels, diagnostics, and string cleanup | medium | S01 | ✅ | All user-facing strings (branding header, launch panel, doctor output, setup wizard) adapt to the active provider. No hardcoded 'Claude Code' in runtime paths. |
| S04 | Error handling hardening, end-to-end verification, zero-regression gate | medium | S01, S02, S03 | ⬜ | All error paths produce typed, user-facing errors. Full test suite passes. Both providers verified end-to-end. |
