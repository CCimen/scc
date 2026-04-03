# Spec 04 — Runtime And Enforced Web Egress

## Objective
Ship a portable OCI runtime with honest and enforceable web egress control.

## Runtime targets
- plain OCI first
- Docker Engine / OrbStack / Colima-style Docker CLI first
- Podman next
- no Docker Desktop dependency

## Network modes
- `open`
- `web-egress-enforced`
- `locked-down-web`

## Enforced topology
- agent on internal-only network
- proxy is the only component with internal + external attachment
- no host networking
- deny IP literals by default
- deny loopback, private, link-local, and metadata endpoints by default
- ACLs evaluate requested host and resolved IP/CIDR

## Governance
- org sets baseline mode, named sets, and delegation rules
- teams may widen only within delegated bounds
- projects/users may narrow only
