# M010 - Enterprise Workflow Readiness

## Purpose

Make SCC easier to explain, audit, and operate for organizations by tightening the project/team switching story, effective configuration explanation, and docs truth. This milestone starts with ownership reconciliation because the current code already has several relevant owners; adding a parallel model first would create debt.

## Source-grounded gap map

| Finding | Status | Evidence | Already-owned-by | Reuse/Evolve/Add | Next action |
|---|---|---|---|---|---|
| Milestone numbering must not reuse old IDs | Done in S01 | `.gsd/PROJECT.md` records M001-M009 as complete; external feedback called its next step M006 | `.gsd/PROJECT.md` | Reuse | Track this work as M010 and number later roadmap items M011+ |
| Stale M001 milestone files misled agents | Cleaned in S01 | `.gsd/milestones/` only contained M001 files while `.gsd/PROJECT.md` showed M001-M009 complete | `.gsd/PROJECT.md` | Delete | Keep only current/future milestone artifacts under `.gsd/milestones/` |
| Effective context should not become a parallel stack | Done through S04 | `EffectiveConfig` remains the effective-config result; typed result models now live in `src/scc_cli/application/effective_config_models.py` and merge logic stays in `compute_effective_config.py` | Effective-config application layer | Move + evolve | Project policy narrowing and ignored policy traces reuse this owner; no `EffectiveContext` stack added |
| Explainability already has a CLI surface | Implemented in S04 | `scc config explain` renders effective network policy plus ignored team/project policy changes; JSON includes `ignored_policy_changes` | Config command plus effective-config decisions | Evolve | Keep `scc config explain` as the explanation surface; do not add `scc explain` in M010 |
| Project and workspace identity already have a context owner | Done in S03 | `WorkContext` tracks team, repo root, worktree path, branch, pinned state, session id, and provider id; D052 records repo+worktree as v1 project identity | `contexts.py` | Reuse | No project registry or `.scc.yaml` `project_name` field in M010 |
| Project/user policy must only narrow org/team policy | Implemented in S02/S04 | `tests/test_effective_context_project_policy.py` proves project config cannot widen and can narrow network policy; ignored widening now appears in explain output | Effective-config policy merge | Evolve | Maintain project network-policy validation at `.scc.yaml` read edge |
| Docs truth needs a claim audit, not another narrative page | Done in S05 | Docs updated for project network-policy tightening, ignored policy changes, removal of stale `entry_directory`, and topology-enforced network wording | Docs repo plus source truth | Reuse | Use targeted claim updates and Astro validation rather than broad narrative rewrites |
| Stats launch tests were dead scaffolding | Cleaned in S04 | `tests/test_stats_launch.py` had only fixtures and no tests; `record_session_start` has no production caller | Stats subsystem | Delete/defer | Deleted fixture-only test file; defer stats wiring/deletion to a separate milestone |
| Runtime/devcontainer interoperability is real but premature | Deferred | Constitution and PLAN make runtime isolation core; no project context model exists yet to express devcontainer attachment safely | Runtime adapters and launch planning | Defer | Revisit as M011 after project context and explainability are typed |
| SSO, SCIM, SBOM, and audit export are enterprise roadmap items | Deferred | Constitution says enterprise value sits above local runtime in identity, policy, audit export, secrets, and support | Future enterprise layer | Defer | Do not implement before project context, audit event shape, and explanation outputs are stable |
| Performance work is not the first bottleneck | Watch | `compute_effective_config.py` is 710 lines after model extraction; `contexts.py` caps records at 30 and uses simple local JSON operations | Current source owners | Reuse | Keep effective-config merge logic below the hotspot zone; optimize only from measured/runtime evidence |

## Planned slices

1. S01 - Done: gap map and ownership cleanup removed stale M001 milestone artifacts, registered M010, and reconciled external feedback with source owners.
2. S02 - Done: project policy narrowing proof added `tests/test_effective_context_project_policy.py` and implemented project `network_policy` narrowing in the existing effective-config owner.
3. S03 - Done: project/workspace switching model recorded in D052; no new registry or project-name field added.
4. S04 - Done: `scc config explain` now surfaces ignored project network-policy widening in human and JSON output, validates project `network_policy`, and reflects topology-enforced network policy status.
5. S05 - Done: docs claim cleanup removed stale `entry_directory` guidance and updated project/network-policy inheritance and explainability wording.
6. S06 - Done: enterprise pilot blueprint added as a minimal, truth-anchored organization-admin guide without implementing SSO, SCIM, SBOM, devcontainer orchestration, or a project registry.

## Non-goals

- Do not add a new `EffectiveContext` stack before proving the existing effective-config owner cannot evolve.
- Do not add `scc explain` as a second explanation command while `scc config explain` already owns the behavior.
- Do not build SSO, SCIM, SBOM, devcontainer orchestration, or new git-provider integrations in M010/S01-S04.
- Do not optimize local JSON context storage unless profiling or data volume proves it matters.
