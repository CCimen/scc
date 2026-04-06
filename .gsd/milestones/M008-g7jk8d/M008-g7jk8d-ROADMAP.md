# M008-g7jk8d: Cross-Flow Consistency, Reliability, and Maintainability Hardening

## Vision
Every user-facing flow (setup, start, dashboard resume, dashboard worktree start, worktree create, doctor) uses the same launch preflight orchestration: resolve provider → collect readiness → ensure image → ensure auth → launch. Stale Docker Desktop assumptions are removed from active paths. Auth/readiness wording is truthful and consistent across all surfaces (distinguishing auth cache present, image present, and launch-ready). Error messages give actionable SCC guidance. Session recording threads provider_id through all context objects. The five current copies of the launch preflight sequence collapse into one shared module. SCC list/stop/status/resume all operate on the same SCC-managed inventory. Product branding stays 'Sandboxed Coding CLI' per D045.

## Slice Overview
| ID | Slice | Risk | Depends | Done | After this |
|----|-------|------|---------|------|------------|
| S01 | Provider resolution consistency across worktree create and wizard flow | high | — | ⬜ | worktree create --start uses choose_start_provider() with full precedence. run_start_wizard_flow() reuses shared resolution. WorkContext records provider_id. start_claude renamed. |
| S02 | Auth/readiness wording truthfulness, Docker Desktop cleanup, and adapter dispatch consolidation | medium | S01 | ⬜ | Doctor, setup summary, and choose-provider screen use consistent auth vocabulary. No 'Docker Desktop' in active error paths. Provider adapter dispatch uses shared lookup. |
| S03 | Error quality, edge case hardening, and final verification | low | S01, S02 | ⬜ | Error messages give actionable SCC guidance. Edge cases (both providers connected, none connected, explicit --provider with missing auth, failed launch doesn't write workspace preference) handled correctly. |
