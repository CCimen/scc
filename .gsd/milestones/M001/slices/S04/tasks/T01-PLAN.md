---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T01: Add typed M001 control-plane contracts

Introduce the M001 typed contract layer for the planned control-plane seams: RuntimeInfo, ProviderCapabilityProfile, AgentLaunchSpec, NetworkPolicyPlan, DestinationSet, EgressRule, SafetyPolicy, SafetyVerdict, and AuditEvent. Keep the first implementation thin and provider-neutral.

## Inputs

- `Spec 02`
- `Spec 03`
- `Spec 04`
- `S03 characterization tests`

## Expected Output

- `Typed core models in code with minimal integration points.`
- `Contract-oriented tests or diagnostics proving the models compile and are usable.`

## Verification

uv run mypy src/scc_cli && uv run pytest -k "contract or typed or launch spec or runtime info or safety verdict or audit event"
