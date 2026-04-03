# Spec 02 — Control Plane And Types

## Objective
Make application-layer policy and launch planning typed and provider-neutral.

## Required models
- `RuntimeInfo`
- `ProviderCapabilityProfile`
- `AgentLaunchSpec`
- `NetworkPolicyPlan`
- `DestinationSet`
- `EgressRule`
- `SafetyPolicy`
- `SafetyVerdict`
- `AuditEvent`

## Rules
- Raw dictionaries may exist only at parsing and serialization boundaries.
- Human CLI and JSON output must share a stable error category model.
- Audit event shape must be shared by network and safety paths.
