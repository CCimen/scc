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
- `GovernedArtifact`
- `ArtifactBundle`
- `ArtifactInstallIntent`
- `ProviderArtifactBinding`
- `ArtifactRenderPlan`

## Rules
- Raw dictionaries may exist only at parsing and serialization boundaries.
- Human CLI and JSON output must share a stable error category model.
- Audit event shape must be shared by network and safety paths.
- Org/team/project/user artifact intent must be expressed in provider-neutral models, not
  in `.claude` or `.codex` file shapes.
- Shared skills, MCP definitions, and provider-native integrations must carry provenance,
  pinning, approval state, and installation intent in one typed control-plane model.
- Provider adapters may render native artifacts from an `ArtifactRenderPlan`, but the
  control plane must not treat provider plugin references as the canonical policy shape.
