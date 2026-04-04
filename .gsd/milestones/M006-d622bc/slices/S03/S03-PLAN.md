# S03: Provider-aware branding, panels, diagnostics, and string cleanup

**Goal:** Make all user-facing and machine-readable surfaces provider-aware: TUI (launch panel, dry-run, active stack, dashboard, sessions, containers, quick resume), doctor readiness (separate backend from provider, actionable build commands), machine-readable outputs (dry-run JSON, support bundle, session/container list --json), branding (SCC-neutral shared surfaces), and feature gating (Claude-only features hidden under Codex).
**Demo:** After this: All user-facing strings (branding header, launch panel, doctor output, setup wizard) adapt to the active provider. No hardcoded 'Claude Code' in runtime paths.

## Tasks
