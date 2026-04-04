# SCC Product Constitution

These are the non-negotiable rules for evolving SCC.

## 1. SCC is a governed runtime, not a new coding agent
SCC competes by governing, isolating, configuring, and operating existing coding agents safely. It does not compete by inventing another general-purpose agent.

## 2. The governance model is the moat
Org → team → project inheritance, delegation, workspace pinning, sessions, and auditability are product assets, not incidental implementation details.

## 3. No hard Docker Desktop dependency
Docker Desktop may be supported, but SCC must work through portable OCI runtimes and should remain open to Podman and WSL-first workflows.

## 4. Security language must match actual enforcement
Do not call a mode "isolated" unless the runtime actually enforces it. Advisory behavior must be described as advisory.

## 5. Least privilege by default
Provider-core access may be automatic for the selected provider, but all broader egress and integration surfaces must be allowlist-driven.

## 6. Provider-specific behavior belongs in adapters
Core code must not depend on Claude-specific or Codex-specific paths, config layouts, hook semantics, or plugin details.

## 7. Typed contracts over loose dictionaries
Raw dictionaries are allowed only at parsing and serialization boundaries. Internal control-plane and runtime planning must use typed models.

## 8. Open Agent Skills, not proprietary SCC skills
Skills are the shared portability surface. SCC governs provenance, pinning, and installation intent, but does not invent a new SCC-only skill format.

## 9. Runtime-level safety beats provider luck
Provider-native hooks, rules, and plugins are helpful UX layers, not the hard enforcement plane.

## 10. WSL-first on Windows is acceptable
Cross-platform support should be pragmatic and testable. WSL-first is acceptable for v1.

## 11. No architecture rewrite until the synced baseline is green
All major work starts from `scc-sync-1.7.3` with a green baseline and preserved rollback evidence.

## 12. Open-source local runtime, optional enterprise layer
The local runtime stays inspectable and open. Enterprise value sits above it in identity, policy management, audit export, secrets, and support.

## 13. Maintainability is a first-class requirement
When touching a large or fragile area, leave it more modular, more typed, better tested, and easier to change. Prefer focused extractions, clear composition roots, and characterization tests over temporary convenience.

## Amendment rule
Any change to this constitution must be reflected in `.gsd/DECISIONS.md`, the main plan, and the affected specs in the same change.
