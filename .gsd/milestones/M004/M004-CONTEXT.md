# M004 Context: Cross-Agent Runtime Safety

## Milestone Intent
M004 turns the current safety direction into a real shared enforcement plane. The result should be one SCC-owned safety baseline that both providers consume, with provider-native integrations acting only as UX and audit helpers.

## Sequencing
M004 runs after M003 and before M005.

Reason:
- it depends on the runtime and topology contracts established in M003
- it still changes runtime/safety seams that M005 should harden only after they stabilize

## In Scope
- shared safety engine and typed verdicts
- SCC-owned runtime wrappers for the first safety command families
- provider UX/audit adapters for Claude and Codex
- fail-closed policy loading and truthful diagnostics
- truthful safety diagnostics about provider capabilities, active team context, and which
  provider-native safety surfaces are present vs merely planned
- truthful differentiation between Codex rules/hooks surfaces and Codex plugin surfaces when
  reporting current capability status
- local helper extractions only where active safety work needs them

## Out Of Scope
- new provider support
- new network-policy surface area beyond the M003 runtime boundary
- repo-wide strict typing or decomposition work reserved for M005
- expansion to package managers, cloud CLIs, or other command families outside the first safety scope
- full Codex plugin/materialization parity; M004 should surface truthful status, not invent it
