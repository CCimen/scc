# M003-ROADMAP.md

# Milestone M003 — Portable Runtime And Enforced Web Egress

## Outcome
SCC launches Claude and Codex on a provider-neutral, capability-based runtime surface with truthful enforced web-egress topology that does not depend on Docker Desktop or provider-native networking claims.

## Slices
- [ ] Replace name-based runtime detection with typed capability-based `RuntimeInfo`
- [ ] Build SCC-owned OCI image contracts for `scc-base`, `scc-agent-claude`, `scc-agent-codex`, and `scc-egress-proxy`
- [ ] Ship the plain OCI backend for Docker Engine, OrbStack, and Colima-style Docker CLIs on one shared contract
- [ ] Enforce web-egress topology with an internal-only agent container and a dual-homed proxy container
- [ ] Deny IP literals plus loopback, private, link-local, and metadata destinations by default, with host and resolved-IP ACL checks
- [ ] Use named destination sets owned by org/team policy, with project/user scopes allowed to narrow but not widen
- [ ] Keep one active team context per session/workspace rather than implicitly unioning team access
- [ ] Keep M003 maintainability work local to touched runtime and egress files; reserve repo-wide quality sweeps for M005

## Dependencies
- M002 complete

## Risk level
High

## Done when
- runtime capability detection is typed and portable
- SCC-owned image contracts exist for the runtime and proxy roles
- enforced web-egress mode is implemented by SCC-controlled topology and proxy policy, not by naming alone
- effective policy resolves from org/team/project/user scope into real allowed destinations and truthful diagnostics
- Docker Desktop is not a required dependency
- verification passes on the active branch with truthful runtime and egress diagnostics
