# GSD Overrides

User-issued overrides that supersede plan document content.

---
## Override: 2026-04-03T21:37:02.620Z

**Change:** Keep milestone order M002 -> M003 -> M004 -> M005.
  Do not promote M005 ahead of M003 or M004.
  In M002-M004, allow only local maintainability extractions that directly enable the active slice in touched files.
  Reserve repo-wide decomposition, typed config migration, guardrail restoration, xfail removal, and the broad coverage campaign for M005.
  When reassessing the roadmap, preserve M005 as the final quality-bar milestone
**Scope:** resolved
**Applied-at:** M002/S05/none

---

## Override: 2026-04-03T21:40:41.015Z

**Change:** After M002 completes, do not start M005 next.
  Create/register M003 and M004 from PLAN.md and run milestones in this order:
  M003 -> M004 -> M005.

  M003 = Portable Runtime And Enforced Web Egress.
  M004 = Cross-Agent Runtime Safety.
  M005 = Architecture Quality, Strictness, And Hardening.

  Keep M005 as the final quality-bar milestone.
  In M003 and M004, allow only local maintainability extractions that directly enable the active slice in touched files.
  Do not pull repo-wide decomposition, broad typed-config migration, guardrail restoration, xfail removal, or the large coverage campaign forward before M005.
**Scope:** resolved
**Applied-at:** M002/S05/none

---

## Override: 2026-04-04T10:29:52.388Z

**Change:** For the rest of M003, keep the enterprise egress model explicit:
  - web-egress-enforced is the normal cloud-provider enterprise mode
  - locked-down-web is an intentional no-web / no-cloud-launch posture unless a future local-model path exists
  - org owns baseline mode, hard deny overlays, named destination sets, and delegation
  - teams may widen only within delegated bounds
  - project/user scopes may narrow only
  - every workspace/session has exactly one active team context
  - users switch context between teams such as Draken and Eneo; do not implicitly union team allowlists
  - diagnostics must show active team context, effective destination sets, runtime backend, network mode, and clear blocked reasons
  - topology plus proxy policy remain the hard control; wrappers are defense-in-depth, UX, and audit only
**Scope:** resolved
**Applied-at:** M003/S04/T03

---

## Override: 2026-04-04T11:54:39.634Z

**Change:** For M004/S02-S05, keep the safety architecture narrow and truthful.

  S02:
  - Put the first SCC-owned runtime wrappers in scc-base.
  - Scope is destructive git plus explicit network tools only: curl, wget, ssh, scp, sftp, remote rsync.
  - Keep wrappers small, typed, and fail-closed.
  - Do not expand to package managers, cloud CLIs, kubectl, terraform, or broad command families.

  Cross-slice rules:
  - In enforced web-egress modes, topology plus proxy policy remain the hard network control.
  - Network-tool wrappers are defense-in-depth, early UX, and audit only.
  - Do not imply wrappers are the primary enforcement plane for network isolation.
  - Keep provider-native integrations adapter-owned and additive only.
  - Keep one active team context per session/workspace in diagnostics and safety surfaces; no implicit union of team access.
  - Keep M004 maintainability work local to touched files; do not pull M005-style broad cleanup forward.
**Scope:** resolved
**Applied-at:** M004/S02/none

---

## Override: 2026-04-04T14:25:00.000Z

**Change:** When M005 planning begins, implement the governed-artifact and team-pack refactor using the provider-neutral bundle model already defined in the plan/spec/decision set.

  Required reread before planning or implementation:
  - `CONSTITUTION.md`
  - `PLAN.md`
  - `.gsd/DECISIONS.md`
  - `.gsd/KNOWLEDGE.md`
  - `specs/03-provider-boundary.md`
  - `specs/06-governed-artifacts.md`
  - `.gsd/milestones/M005/M005-ROADMAP.md`
  - `.gsd/milestones/M005/M005-CONTEXT.md`

  Implementation direction:
  - One approved SCC team-pack source is canonical.
  - Team config references approved bundle/team-pack IDs, not raw Claude or Codex marketplace URLs.
  - Preserve the user-facing experience of one team package per team.
  - Shared skills and shared MCP definitions stay provider-neutral where possible.
  - Claude and Codex native surfaces are asymmetric.
  - Codex plugin does not subsume Codex rules, hooks, `config.toml`, or `AGENTS.md`.
  - Do not bolt Codex support onto the current Claude-shaped marketplace pipeline.
  - Split provider-neutral planning from provider-native renderers.
  - Render Claude-native outputs for Claude and Codex-native outputs for Codex from the same bundle plan.
  - Do not require dual team configs.

  Preferred execution order inside M005 for this work:
  1. S02/T05 — split the marketplace/profile/config cluster so provider-neutral planning is separate from provider-native renderers.
  2. S03/T01-T03 — land typed governed-artifact/team-pack models and typed config flow.
  3. S04/T01-T05 — harden fetch/render/merge/install failure handling.
  4. S06/T03-T04 — run the docs/diagnostics truthfulness pass and milestone validation after the renderer split is real.

  M004 remains narrow:
  - Finish M004/S04 and M004/S05 normally.
  - Do not start M005 implementation early.
  - In M004, only document current truth and verify truthful safety/provider messaging; do not implement the new team-pack pipeline there.

**Scope:** resolved
**Applied-at:** M004/S04/none

---

## Override: 2026-04-04T16:40:16.270Z

**Change:** Current M005/S02 UI decomposition work is acceptable. Before starting the next S02 task or any S03 work, pause and re-read .gsd/OVERRIDES.md, specs/03-provider-boundary.md, specs/06-governed-artifacts.md, .gsd/milestones/
  M005/M005-CONTEXT.md, and .gsd/milestones/M005/M005-ROADMAP.md.

  Then refine the remaining M005 task plans so the governed-artifact/team-pack architecture is explicit.

  Required implementation direction:
  - one approved SCC team-pack source is canonical
  - team config references bundle/team-pack IDs, not raw Claude or Codex marketplace URLs
  - preserve the user-facing experience of one team package per team
  - split provider-neutral planning from provider-native renderers
  - Claude and Codex native surfaces are asymmetric
  - Codex plugin does not subsume Codex rules, hooks, config.toml, or AGENTS.md
  - do not bolt Codex support onto the current Claude-shaped marketplace pipeline
  - render Claude-native outputs for Claude and Codex-native outputs for Codex from the same bundle plan
  - do not require dual team configs

  S02 must still include the marketplace/profile/config cluster split needed for this architecture, not only generic size reduction.
**Scope:** resolved
**Applied-at:** M005/S02/T06

---

## Override: 2026-04-04T16:43:11.295Z

**Change:** Finish the current T06 cleanly, but do not continue into generic S03 work.

  Before starting S03 or any further M005 implementation, stop and replan S03-S06 using the governed-artifact/team-pack architecture already defined in:
  - .gsd/OVERRIDES.md
  - specs/03-provider-boundary.md
  - specs/06-governed-artifacts.md
  - .gsd/milestones/M005/M005-CONTEXT.md
  - .gsd/milestones/M005/M005-ROADMAP.md

  Required direction:
  - one approved SCC team-pack source is canonical
  - team config references bundle/team-pack IDs, not raw provider marketplace URLs
  - preserve the UX of one team package per team
  - split provider-neutral planning from provider-native renderers
  - Claude and Codex native surfaces are asymmetric
  - Codex plugin does not subsume Codex rules, hooks, config.toml, or AGENTS.md
  - do not bolt Codex support onto the current Claude-shaped marketplace pipeline
  - render Claude-native outputs for Claude and Codex-native outputs for Codex from the same bundle plan
  - do not require dual team configs

  This means:
  - S03 must explicitly land typed governed-artifact/team-pack models and typed config flow
  - S04 must explicitly harden fetch/render/merge/install failure handling for native renderers
  - S06 must explicitly validate docs/diagnostics truthfulness for the team-pack model

  Do not proceed with generic S03 strict-typing cleanup until these task plans are rewritten to include the team-pack refactor.
**Scope:** resolved
**Applied-at:** M005/S02/T06

---

## Override: 2026-04-04T20:10:00.000Z

**Change:** Finish S03 T04 cleanly (already done). Before starting T05 or any S04 work, stop and rewrite the remaining M005 task plans around the governed-artifact/team-pack architecture.

  What is already done and preserved:
  - typed governed-artifact foundation landed in S03/T01
  - NormalizedOrgConfig adoption in T02-T04 is acceptable

  What was still missing and is now explicit in the replanned S04-S06:
  - one approved SCC team-pack source is canonical
  - team config references bundle/team-pack IDs, not raw Claude or Codex marketplace URLs
  - preserve the UX of one team package per team
  - split provider-neutral planning from provider-native renderers
  - Claude and Codex native surfaces are asymmetric
  - Codex plugin does not subsume Codex rules, hooks, config.toml, or AGENTS.md
  - do not bolt Codex support onto the current Claude-shaped marketplace pipeline
  - render Claude-native outputs for Claude and Codex-native outputs for Codex from the same bundle plan
  - do not require dual team configs

  Replan completed:
  - S03 closed with T01-T04 done, T05 deferred (dict count already under target)
  - S04 rewritten: provider-neutral artifact planning pipeline + provider-native renderers + failure hardening
  - S05 rewritten: coverage on governed-artifact/team-pack planning and renderer seams
  - S06 rewritten: diagnostics/docs truthfulness for team-pack model + guardrails + milestone validation
  - Decision D021 recorded
**Scope:** resolved
**Applied-at:** M005/S03/T05

---

## Override: 2026-04-05T14:16:09.080Z

**Change:** Do not close M007 as docs-only yet. The final M007 architecture and the current code are still out of sync in a few important places, and S05 must include reconciliation tasks before milestone closeout.

  Current state I want you to address explicitly:
  - S05 has no tasks yet.
  - S01-S04 are marked complete.
  - The roadmap/context now promise stronger architecture than the code currently provides.
  - Do not paper over those gaps with documentation.

  Please add explicit S05 reconciliation tasks or reopen implementation work before final validation.

  Required reconciliation items:

  1. Implement D041 for real, not only in docs.
  - The final M007 context says SCC uses provider-native config layering:
    - Claude: SCC-owned settings.json layer, user-owned settings.local.json
    - Codex: SCC-owned project-scoped .codex/config.toml layer, user-owned ~/.codex/config.toml untouched
  - Current code still builds settings under /home/agent using spec.settings_path.
  - Implement the actual ownership model so Codex SCC-managed config is not treated like home-level provider config.
  - If the chosen Codex overlay is workspace-scoped .codex/config.toml, handle repo cleanliness explicitly:
    - either ensure .codex is excluded/ignored safely without mutating tracked files unexpectedly
    - or use a different SCC-managed sidecar path / launch mechanism
  - Do not let SCC silently dirty user repos.
  - Add tests for repo cleanliness / expected ignored behavior.

  2. Implement D035 for real: provider-owned settings serialization.
  - Current OCI runtime still does json.dumps(spec.agent_settings.content) for all providers.
  - That is not provider-neutral and is structurally wrong for Codex TOML.
  - Refactor so AgentRunner or a provider-owned settings renderer produces final rendered text/bytes plus target path.
  - OCI runtime must copy rendered content verbatim and must not serialize provider config itself.
  - Update contracts accordingly.
  - Add tests proving:
    - Claude settings render as JSON to the Claude target
    - Codex settings render as TOML to the Codex target
    - runtime no longer assumes JSON

  3. Implement D033 for real: Codex launch policy.
  - Current codex runner still launches plain `codex`.
  - Final M007 context says the in-container policy is `codex --dangerously-bypass-approvals-and-sandbox`.
  - Either implement D033 exactly and test it, or explicitly revise D033 if you determine a different policy is correct.
  - Do not leave the docs saying one thing and the code doing another.
  - Keep this runner-owned, not runtime-spec-owned.

  4. Implement D040 for real: file-based Codex auth in containers.
  - Codex auth persistence must support “login once, reuse until token expiry/refresh”.
  - In the containerized Codex path, force `cli_auth_credentials_store = "file"` via the SCC-managed Codex config layer.
  - Do not rely on keyring/auto behavior inside containers.
  - Ensure refreshed auth writes back to the persistent provider volume.
  - Add tests around:
    - presence of file-based auth config in the SCC-managed Codex layer
    - auth persistence across container restarts
    - no forced re-login on every start when auth cache is still valid

  5. Finish D037 properly: adapter-owned auth readiness, not only doctor-local file checks.
  - Current check_provider_auth is useful but still uses local provider→filename mapping and only basic file existence probing.
  - Move auth readiness ownership to the provider adapter boundary (for example provider.auth_check(data_volume) -> AuthReadiness or equivalent).
  - Doctor should consume the provider-owned auth readiness result.
  - Auth wording must stay truthful:
    - say “auth cache present” if the check is local and non-networked
    - do not imply “logged in” or “validated” unless that is actually checked
  - Improve the local readiness quality:
    - at minimum require file existence plus non-empty content
    - parseable JSON for providers that use JSON auth files if feasible
  - Keep validated/networked auth checks out of scope unless deliberately added.

  6. Remove remaining active-launch Claude fallbacks.
  - D032 says active launch logic fails closed.
  - Check and eliminate any remaining launch/runtime paths that still substitute Claude when provider wiring is missing or unknown.
  - In particular, active launch logic must not silently choose Claude if agent_provider is absent or provider identity is invalid.
  - Missing provider wiring should surface a typed launch error, not a Claude fallback.

  7. Strengthen the persistence model implementation, not just the docs.
  - The current “one provider volume per provider” model is acceptable for v1, but config freshness must be deterministic.
  - Implement D038/D042 fully:
    - on every fresh launch, SCC writes or clears its own managed config layer deterministically
    - on resume, the original session config remains
  - Add tests for:
    - governed launch -> standalone launch
    - team A -> team B
    - settings -> no-settings
  - Do not rely on fresh container creation alone for freshness.

  8. Implement runtime permission normalization robustly.
  - Build-time Dockerfile permissions are not enough.
  - Runtime launch must normalize mounted provider state permissions where needed:
    - provider state dir 0700
    - auth files 0600
    - uid 1000 ownership
  - Keep this scoped to provider state/auth paths, not broad recursive chmod on unrelated mounts.
  - Add tests for the normalization command construction.

  9. Finish image hardening.
  - scc-base should prepare both ~/.claude and ~/.codex with correct ownership/permissions.
  - scc-agent-codex should pin the Codex package version, ideally via ARG, not floating latest.
  - Keep image builds deterministic and document the upgrade path.
  - Ensure doctor/build guidance matches the actual image tags and build commands.

  10. Keep architecture clean and avoid unnecessary churn.
  - The highest priority is behavior, ownership, auth persistence, and truthfulness.
  - Do not spend time moving provider_registry purely for module-placement aesthetics unless it materially helps these goals.
  - If current provider_registry placement is acceptable after the behavior is fixed, update the docs/decisions accordingly instead of churning code just to satisfy an earlier wording choice.

  11. Expand S05 to include truthfulness validation against code, not only docs.
  - README/product naming update is still required.
  - But S05 must also verify that the final decisions D033/D035/D037/D040/D041 are reflected in code and tests before milestone closeout.
  - If these items do not fit cleanly into S05, explicitly add new S05 tasks or reopen the relevant slice. Do not mark M007 complete while these remain doc-only promises.

  Acceptance criteria to add before M007 close:
  - Codex SCC-managed config uses the intended ownership/layering model and does not unintentionally overwrite user-owned config.
  - SCC does not dirty user repos unexpectedly when applying the Codex config layer.
  - Agent settings serialization is provider-owned; OCI runtime copies bytes/text verbatim and no longer assumes JSON.
  - Codex launch argv matches the recorded decision D033, or D033 is explicitly revised and implemented consistently.
  - Codex auth cache persists across container restarts without forcing re-login each time.
  - Doctor reports truthful backend/image/auth readiness without overstating validation.
  - Active launch logic never silently falls back to Claude for unknown/missing providers.
  - README, docs, and UI naming are consistent with “SCC — Sandboxed Code CLI”.

  Please update the plan and implement these reconciliation tasks before treating S05 as pure docs/validation."
**Scope:** active
**Applied-at:** M007-cqttot/S05/T01

---
