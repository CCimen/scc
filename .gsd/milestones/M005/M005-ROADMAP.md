# M005: M005: Architecture Quality, Strictness, And Hardening

## Vision
M005: Architecture Quality, Strictness, And Hardening

## Slice Overview
| ID | Slice | Risk | Depends | Done | After this |
|----|-------|------|---------|------|------------|
| S01 | Maintainability baseline and refactor queue | medium | — | ✅ | TBD |
| S02 | Decompose oversized modules and repair boundaries | high | S01 | ✅ | TBD |
| S03 | Typed config model adoption and strict typing cleanup | high | S02 | ✅ | TBD |
| S04 | Provider-neutral artifact planning pipeline and provider-native renderers with hardened failure handling | high | S03 | ✅ | Team config references bundle IDs; SCC resolves bundles to ArtifactRenderPlan; Claude adapter renders settings.local.json + marketplace from plan; Codex adapter renders plugin + rules + hooks from same plan; fetch/render failures are fail-closed with clear diagnostics |
| S05 | Coverage on governed-artifact/team-pack planning and renderer seams | medium | S03, S04 | ✅ | Contract tests verify bundle resolution, render plan computation, and both provider renderers; failure paths (missing bundles, invalid bindings, renderer errors) have explicit test coverage |
| S06 | Diagnostics, docs truthfulness, guardrails, and milestone validation for team-pack model | medium | S03, S04, S05 | ✅ | Diagnostics show active team context, effective bundles, shared vs native, rendered/skipped/blocked; docs claims match implementation; file-size/complexity guardrails pass without xfail; milestone validation passes |
| S07 | Render portable artifacts from effective_artifacts without provider bindings (D023) | medium | S04, S05 | ✅ | TBD |
