# M003 Context: Portable Runtime And Enforced Web Egress

## Milestone Intent
M003 establishes the runtime and network-enforcement foundation that the rest of SCC depends on. The milestone must make portability and web-egress claims true in the implementation, not just in naming or UX.

## Sequencing
M003 runs after M002 and before M004/M005.

Reason:
- M004 depends on a stable runtime boundary to place safety wrappers correctly.
- M005 should harden and decompose the final runtime/safety surfaces after they stop moving.

## In Scope
- capability-based `RuntimeInfo`
- SCC-owned image contracts and plain OCI backend
- enforced web-egress topology and proxy ACLs
- truthful runtime and egress diagnostics
- local helper extractions only where runtime/egress work directly needs them

## Out Of Scope
- repo-wide maintainability sweeps
- broad typed-config migration outside touched runtime/egress seams
- new provider support
- the shared safety-engine extraction reserved for M004
