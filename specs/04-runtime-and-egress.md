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

## Control model
- `open` is the low-friction mode and should not make hard isolation claims
- `web-egress-enforced` is the recommended enterprise mode when external web access is needed with bounded destinations
- `locked-down-web` is the strictest mode and must block launches that require provider-core web access
- v1 enforced egress is HTTP/HTTPS-focused only and must not be described as generic arbitrary TCP/UDP isolation

## Governance model
- org policy owns the baseline mode, hard deny overlays, the named destination-set catalog, and delegation rules
- team policy may widen effective egress only within org-delegated bounds, typically by selecting approved named destination sets
- project and user scopes may narrow only; they must not widen effective egress in v1
- named destination sets are the primary abstraction, not raw per-user host lists
- provider-core destination sets are automatic for the selected provider only; broader developer or internal service access remains an explicit org/team choice

## Active team context
- every workspace/session runs under exactly one active team context
- users who belong to multiple teams switch context between those teams; SCC must not implicitly union multiple team allowlists for one session
- if a combined posture is genuinely needed, it should be published as an explicit reviewed team profile rather than assembled ad hoc on a laptop

## Enforcement details
- in `web-egress-enforced`, SCC-computed proxy settings are authoritative; inherited host proxy environment variables must not weaken or override enforced behavior
- the agent container gets exactly one internal-only network attachment in enforced mode
- the proxy sidecar is the only component attached to both the internal network and an egress-facing network
- topology plus proxy policy are the hard control; wrappers and provider-native integrations are defense-in-depth, UX, and audit layers
- hard deny overlays remain active even when a destination set would otherwise widen access

## Truthfulness requirements
- SCC must not claim "isolated" or "cannot reach company systems" unless the runtime topology and policy on the active backend actually enforce that statement
- if IPv6 is not enforced in v1, SCC must either disable it in the enforced path or state clearly that enforced egress is IPv4-only for now
- operator diagnostics must answer which runtime/backend is active, which team context is active, which mode is active, which destination sets are effective, and why a launch or request was blocked

## Governance
- org sets baseline mode, named sets, and delegation rules
- teams may widen only within delegated bounds
- projects/users may narrow only
