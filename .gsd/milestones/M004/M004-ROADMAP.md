# M004: Cross-Agent Runtime Safety

## Vision
Give Claude and Codex one shared, typed, fail-closed runtime safety layer owned by SCC rather than by provider-native integrations.

## Slice Overview
| ID | Slice | Risk | Depends | Done | After this |
|----|-------|------|---------|------|------------|
| S01 | Shared safety policy and verdict engine | high | — | ⬜ | Safety decisions are produced by one provider-neutral engine with typed verdicts. |
| S02 | Runtime wrapper baseline in `scc-base` | high | S01 | ⬜ | Hard enforcement lives in SCC-owned wrappers rather than provider-native hooks. |
| S03 | Claude and Codex UX/audit adapters over the shared engine | medium | S01, S02 | ⬜ | Provider-native integrations improve UX and visibility without becoming the sole enforcement path. |
| S04 | Fail-closed policy loading, audit surfaces, and operator diagnostics | medium | S02, S03 | ⬜ | Safety failures block clearly, and diagnostics remain truthful about what is and is not enforced. |
| S05 | Verification, docs truthfulness, and milestone closeout | medium | S03, S04 | ⬜ | M004 exits green with the shared safety surface locked in ahead of M005 hardening. |
