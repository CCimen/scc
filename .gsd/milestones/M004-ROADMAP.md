# M004-ROADMAP.md

# Milestone M004 — Cross-Agent Runtime Safety

## Outcome
SCC enforces the first shared runtime safety baseline for Claude and Codex through SCC-owned wrappers and a provider-neutral safety engine, with provider-native integrations kept additive rather than authoritative.

## Slices
- [ ] Extract the shared `SafetyEngine.evaluate(...) -> SafetyVerdict` seam and typed safety policy models
- [ ] Move the hard baseline into runtime wrappers shipped in `scc-base`
- [ ] Cover destructive git and explicit network tools: `curl`, `wget`, `ssh`, `scp`, `sftp`, and remote `rsync`
- [ ] Keep Claude hooks and Codex-native integrations as UX and audit adapters only
- [ ] Fail closed when safety policy cannot be loaded, validated, or applied
- [ ] Keep M004 maintainability work local to touched safety/runtime files; reserve broad hardening and guardrails for M005

## Dependencies
- M003 complete

## Risk level
High

## Done when
- a shared safety engine produces typed verdicts for both providers
- SCC-owned runtime wrappers enforce the hard baseline
- provider-native integrations are optional UX surfaces, not the only control plane
- the first safety scope covers destructive git and the explicit network tools in plan
- verification passes with truthful safety and audit diagnostics
