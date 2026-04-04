# M003: Portable Runtime And Enforced Web Egress

## Vision
Turn SCC's runtime layer into a portable, typed, provider-neutral OCI backend with truthful enforced web-egress controls.

## Slice Overview
| ID | Slice | Risk | Depends | Done | After this |
|----|-------|------|---------|------|------------|
| S01 | Capability-based runtime model and detection cleanup | high | — | ⬜ | Runtime selection is typed and no longer depends on name-only heuristics. |
| S02 | SCC-owned image contracts and plain OCI backend | high | S01 | ⬜ | SCC can materialize the base, agent, and proxy roles on Docker-compatible OCI runtimes without Docker Desktop assumptions. |
| S03 | Enforced web-egress topology and proxy ACLs | high | S01, S02 | ⬜ | Agent containers are internal-only, the proxy is the only dual-homed component, and default-deny network boundaries are real. |
| S04 | Policy integration, provider destination validation, and operator diagnostics | medium | S02, S03 | ⬜ | Runtime/eject diagnostics are truthful, provider-core requirements stay validated, and blocked destinations fail clearly. |
| S05 | Verification, docs truthfulness, and milestone closeout | medium | S03, S04 | ⬜ | M003 exits green with docs and diagnostics that match actual runtime and egress behavior. |
