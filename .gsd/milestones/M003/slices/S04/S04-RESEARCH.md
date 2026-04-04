# S04 — Research: Policy integration, provider destination validation, and operator diagnostics

**Date:** 2026-04-04

## Summary

S04 bridges the gap between the pure egress policy layer (S03) and the application-level config/launch flow. Currently, `OciSandboxRuntime.run()` calls `build_egress_plan(NetworkPolicy.WEB_EGRESS_ENFORCED)` with **empty** `destination_sets` and `egress_rules` — the proxy ACL gets only default deny rules and a terminal `deny all`, meaning enforced mode would block everything including the provider's own API. There is no mapping from provider-declared `required_destination_sets` names (e.g. `"anthropic-core"`) to concrete `DestinationSet` objects with real hostnames. Operator diagnostics don't cover the new OCI backend, egress topology, or effective network policy.

S04 has three well-scoped deliverables: (1) a provider destination registry that maps named sets to concrete hosts, with the OCI adapter wiring plan construction from effective config + provider destinations, (2) preflight validation that ensures enforced-mode ACLs will include provider-core allow rules before launch, and (3) doctor/diagnostic checks for runtime backend type and effective egress policy. All three are independent at the code level but compose into a coherent "policy reaches runtime" story.

## Recommendation

**Targeted approach using established patterns.** All infrastructure is in place — `DestinationSet`, `EgressRule`, `build_egress_plan()`, `compile_squid_acl()`, the preflight seam, and the doctor check framework. S04 adds small focused modules that wire these together, with no new libraries or risky integration.

Build order: (1) provider destination registry first (pure module, no deps, unblocks everything), (2) policy-to-OCI integration (threads destination sets and allow rules from effective config through SandboxSpec into the OCI adapter's `build_egress_plan()` call), (3) preflight destination validation for enforced mode (extends the existing preflight seam), (4) operator diagnostics (new doctor checks, support bundle section).

## Implementation Landscape

### Key Files

- `src/scc_cli/core/contracts.py` — Already has `DestinationSet`, `EgressRule`, `NetworkPolicyPlan`. No changes needed.
- `src/scc_cli/core/egress_policy.py` — `build_egress_plan()` already accepts `destination_sets` and `egress_rules` params but they're never populated by callers. This file needs no changes — the callers need to pass data.
- `src/scc_cli/core/destination_registry.py` — **New file.** Pure module mapping named destination set IDs (e.g. `"anthropic-core"`, `"openai-core"`) to `DestinationSet` objects with concrete hostnames. Also a `resolve_destination_sets()` function that takes provider required set names and returns typed `DestinationSet` tuples. Constitution §5: "Provider-core access may be automatic for the selected provider, but all broader egress must be allowlist-driven." So provider-core sets produce allow rules; everything else stays deny-by-default.
- `src/scc_cli/ports/models.py` — `SandboxSpec` needs a new optional field `egress_allow_rules: tuple[EgressRule, ...] = ()` (or similar) to carry allow rules from the application layer into the runtime adapter. Alternatively, the OCI adapter can accept the plan as a parameter. The simplest approach: add `destination_sets: tuple[DestinationSet, ...] = ()` to `SandboxSpec` so the OCI adapter can pass them to `build_egress_plan()`.
- `src/scc_cli/adapters/oci_sandbox_runtime.py` — `run()` method currently calls `build_egress_plan(NetworkPolicy.WEB_EGRESS_ENFORCED)` with no destination_sets. Needs to: (1) extract destination_sets from spec, (2) convert provider required_destination_sets to allow-type EgressRules, (3) pass both to `build_egress_plan()`.
- `src/scc_cli/application/start_session.py` — `_build_sandbox_spec()` needs to resolve destination sets from the provider's `required_destination_sets` and the effective config, then pass them into SandboxSpec.
- `src/scc_cli/application/launch/preflight.py` — Currently only blocks locked-down-web with required destinations. For web-egress-enforced mode, should validate that all `required_destination_sets` are resolvable (i.e. exist in the registry) so the operator gets a clear error at preflight, not a silent deny-all ACL.
- `src/scc_cli/doctor/checks/environment.py` — Add a `check_runtime_backend()` that reports whether OCI or Docker Desktop sandbox is the active backend, using the probe.
- `src/scc_cli/doctor/core.py` — Wire new check(s) into the doctor run.
- `src/scc_cli/application/support_bundle.py` — Add a section for effective egress policy / runtime backend to the manifest.

### Build Order

1. **Provider destination registry (pure, no deps)** — `core/destination_registry.py` with `PROVIDER_DESTINATION_SETS` mapping and `resolve_destination_sets()`. This is a pure module with 100% unit-testable logic. Unblocks all downstream work. Concrete hosts for anthropic-core: `api.anthropic.com`, `*.anthropic.com`. For openai-core: `api.openai.com`, `*.openai.com`. These are the minimum provider-core destinations; orgs can define additional named sets via config.

2. **SandboxSpec threading + OCI adapter integration** — Add `destination_sets` field to `SandboxSpec`. Update `_build_sandbox_spec()` in `start_session.py` to resolve provider destination sets and pass them through. Update `OciSandboxRuntime.run()` to pass `spec.destination_sets` to `build_egress_plan()` and generate allow-type `EgressRule`s for the resolved hosts. This is the core policy-to-runtime bridge.

3. **Preflight enforced-mode validation** — Extend `evaluate_launch_preflight()` to check that all `required_destination_sets` resolve to known destination sets when mode is `web-egress-enforced`. Raise a new `LaunchDestinationUnresolvableError` or similar if a provider requires a set that doesn't exist in the registry. This catches misconfiguration at planning time rather than at runtime.

4. **Operator diagnostics** — Add `check_runtime_backend()` to doctor. Add egress/policy section to support bundle manifest. These are additive and don't affect any existing code path.

### Verification Approach

- `uv run pytest --rootdir "$PWD" tests/test_destination_registry.py -q` — new file, covers mapping and resolution
- `uv run pytest --rootdir "$PWD" tests/test_oci_egress_integration.py tests/test_egress_policy.py -q` — existing + new tests for destination-aware plan construction
- `uv run pytest --rootdir "$PWD" tests/test_launch_preflight.py -q` — existing + new tests for enforced-mode destination validation
- `uv run pytest --rootdir "$PWD" tests/test_start_session_image_routing.py -q` — verify SandboxSpec threading doesn't break existing image routing
- `uv run pytest --rootdir "$PWD" tests/test_doctor_checks.py -q` — existing + new check for runtime backend
- `uv run ruff check` — lint clean
- `uv run mypy src/scc_cli` — type clean
- `uv run pytest --rootdir "$PWD" -q` — full suite green, no regressions

## Constraints

- Constitution §5: provider-core destinations are automatic allow rules only for the selected provider. All other egress surfaces remain allowlist-driven. The destination registry must not auto-enable cross-provider destinations.
- Constitution §6: provider-specific behavior belongs in adapters. The destination registry is in `core/` because it's provider-neutral (maps named sets to hosts), but the provider adapters declare which sets they require.
- Constitution §7: typed contracts over loose dicts. Destination sets must use the existing `DestinationSet` dataclass, not raw strings or dicts.
- KNOWLEDGE.md: "Provider-core destinations must be validated before launch. Do not make users discover missing provider access at runtime."
- KNOWLEDGE.md: "GitHub/npm/PyPI are not provider-core. They are optional named destination sets."
- `SandboxSpec` is frozen (`@dataclass(frozen=True)`), so adding a new field with a default is safe — existing construction sites don't break.

## Common Pitfalls

- **Don't add provider hosts to core constants** — Keep the destination registry as a mapping module, not hardcoded into contracts or enums. Provider hosts can change; the registry pattern makes updates trivial.
- **Don't break the Docker Desktop sandbox path** — `DockerSandboxRuntime` doesn't use `build_egress_plan()` at all (Desktop has its own isolation). New `SandboxSpec` fields must have defaults that preserve existing behavior when unset.
- **Don't couple allow-rule generation to the OCI adapter** — The allow-rule generation from destination sets should be in `build_egress_plan()` or a helper called before it, so future Podman or other backends can reuse the same logic.
- **Don't expand `SandboxSpec` with provider-specific fields** — The spec should carry `destination_sets: tuple[DestinationSet, ...]` (typed core contract), not provider IDs or raw host lists. Keep it provider-neutral per D013.

## Open Risks

- The concrete hostnames for provider-core sets (`api.anthropic.com`, `api.openai.com`) may be incomplete — providers may use additional subdomains for auth, streaming, or API versioning. Starting with known API endpoints is correct; operators can add to org-level destination sets for anything beyond provider-core.
- Adding a `destination_sets` field to `SandboxSpec` requires checking all construction sites (tests, fakes, application code). The frozen dataclass with a default `()` mitigates breakage, but a grep for `SandboxSpec(` is essential to verify.
