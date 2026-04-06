# M001-ROADMAP.md

# Milestone M001 — Baseline Freeze And Typed Foundation

## Outcome
The project has a single authoritative repo root, a green migrated baseline, typed control-plane direction, and the first characterization/contract tests needed for safe refactoring.

## Slices
- [ ] Freeze the archived dirty `scc` tree and make `scc-sync-1.7.3` the only writable root
- [ ] Normalize local docs, configs, tests, and terminology to the new truthful network vocabulary
- [ ] Re-run the full verification gate on the synced repo and capture the baseline
- [ ] Add characterization tests around current Claude launch, resume, config inheritance, and safety-net behavior
- [ ] Define typed core contracts: `AgentProvider`, `AgentLaunchSpec`, `RuntimeInfo`, `NetworkPolicyPlan`, `SafetyPolicy`, `SafetyVerdict`, and `AuditEvent`
- [ ] Align `SCCError`, exit-code mapping, and human/JSON output contracts
- [ ] Record accepted decisions and update specs so follow-on work does not invent hidden compatibility or provider leaks

## Dependencies
- none

## Risk level
High

## Done when
- `scc-sync-1.7.3` is the only implementation root in active use
- no stale compatibility aliases remain in planned core surfaces
- the baseline is green
- characterization coverage exists for the most fragile current behavior
- the typed control-plane contracts are written down and accepted
