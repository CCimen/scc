---
id: M001
title: "Baseline Freeze And Typed Foundation"
status: complete
completed_at: 2026-04-03T15:48:40.068Z
key_decisions:
  - Introduce the M001 typed seams as a thin standalone layer first, then adopt them incrementally in later milestones.
  - Rename both network-policy values and enum member names so live code thinks in the truthful vocabulary directly.
  - Make the `SCCError` hierarchy the canonical source of exit-code and category truth.
  - Expose `error_category` and `exit_code` in JSON error payloads while keeping the existing envelope shape stable.
key_files:
  - src/scc_cli/core/contracts.py
  - src/scc_cli/ports/agent_provider.py
  - src/scc_cli/core/enums.py
  - src/scc_cli/core/network_policy.py
  - src/scc_cli/core/errors.py
  - src/scc_cli/core/error_mapping.py
  - src/scc_cli/json_command.py
  - tests/test_launch_proxy_env.py
  - tests/test_network_policy.py
  - tests/test_plugin_isolation.py
lessons_learned:
  - The dirty working tree was less risky than it looked because the fixed gate was already green; inventory first prevented wasted rescue work.
  - Terminology migrations that reuse common English words need targeted verification, not naive whole-word greps.
  - Small, explicit characterization tests at missing seams are more valuable than broad duplicate suites.
  - Stale exception defaults can hide behind mappers for a long time; aligning the source classes removes that ambiguity.
---

# M001: Baseline Freeze And Typed Foundation

**M001 established the synced repo as the only active root, migrated SCC to truthful network vocabulary, added characterization coverage, and introduced the typed control-plane and error/audit foundation on a clean passing gate.**

## What Happened

M001 delivered the baseline freeze and typed foundation the plan called for. The work started by grounding the milestone in repo truth: `scc-sync-1.7.3` was confirmed as the only active implementation root, the dirty worktree was inventoried instead of ignored, and the fixed verification gate was captured on the real baseline. With that baseline understood, the milestone migrated the live network-policy vocabulary to `open`, `web-egress-enforced`, and `locked-down-web` across code, schema, examples, docs, and tests while preserving behavior under the full gate. It then strengthened characterization coverage around the fragile launch/resume, config-policy, and safety seams so follow-on refactors have explicit behavioral protection. Finally, it introduced the new typed contract layer and provider-neutral `AgentProvider` seam, aligned the exception hierarchy with the shared exit-code contract and stable error categories, exposed JSON error metadata consistently, and added the first shared audit-event mapping helper. The milestone closes on a clean passing gate with the planned typed seams and migration work in place.

## Success Criteria Results

- Active implementation root: met. Evidence from S01 canonical-root checks and ongoing execution in `scc-sync-1.7.3`.
- Truthful network vocabulary migration: met. Evidence from S02 code/schema/example/test rename and targeted no-match verification search.
- Green verification baseline and milestone exit gate: met. Evidence from repeated full-gate passes in S01, S02, S03, and final S04 reruns.
- Characterization coverage for fragile behavior: met. Evidence from S03 additions to launch/config/safety tests.
- Typed core seams and shared error/audit direction: met. Evidence from S04 contract module, provider protocol, error-category alignment, and audit-event helper.

## Definition of Done Results

- Milestone slices were planned and executed in risk order: S01 → S02 → S03 → S04.
- The synced repo remained the only active implementation root throughout execution.
- Legacy network mode names were removed from the live code/schema/example/test surfaces targeted by M001.
- Characterization coverage was added for the fragile launch/config/safety seams named in the roadmap.
- Typed control-plane contracts and aligned error/audit direction were added in code.
- The fixed verification gate passed at milestone exit.

## Requirement Outcomes

- Governed-runtime product identity remained intact and unblurred.
- Truthful network enforcement language advanced from planning intent into live implementation surfaces.
- Provider-neutral typed seams now exist in code via `contracts.py` and `AgentProvider`.
- Characterization-first refactoring was satisfied before typed-seam work landed.
- The fixed verification gate remained the milestone exit contract and passed at completion.
- No structured `RXXX` requirement IDs were present in the legacy requirements document, so milestone requirement outcomes remain narrative rather than ID-indexed.

## Deviations

None that invalidate the milestone. Two slice-local verification reruns were needed during S04 to fix a ruff import issue and a mypy-compatible timezone usage issue before the final clean gate pass.

## Follow-ups

Adopt the new `AgentProvider` / `AgentLaunchSpec` seam in the actual launch flow in M002. Route the new `AuditEvent` shape to a persistent sink when network and safety subsystems are ready. Refresh still-active `.gsd` planning prose that refers to old vocabulary when those files are next regenerated.
