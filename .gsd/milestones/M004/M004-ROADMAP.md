# M004: M004: Cross-Agent Runtime Safety

## Vision
M004: Cross-Agent Runtime Safety

## Slice Overview
| ID | Slice | Risk | Depends | Done | After this |
|----|-------|------|---------|------|------------|
| S01 | Shared safety policy and verdict engine | high | — | ⬜ | TBD |
| S02 | Runtime wrapper baseline in `scc-base` | high | S01 | ⬜ | TBD |
| S03 | Claude and Codex UX/audit adapters over the shared engine | medium | S01, S02 | ⬜ | TBD |
| S04 | Fail-closed policy loading, audit surfaces, and operator diagnostics | medium | S02, S03 | ⬜ | TBD |
| S05 | Verification, docs truthfulness, and milestone closeout | medium | S03, S04 | ⬜ | TBD |
