---
id: S04
parent: M003
milestone: M003
provides:
  - Provider destination registry (PROVIDER_DESTINATION_SETS, resolve_destination_sets, destination_sets_to_allow_rules)
  - SandboxSpec.destination_sets field for carrying resolved sets through the launch pipeline
  - Enforced-mode preflight validation for unresolvable destination sets
  - check_runtime_backend() doctor check
  - effective_egress support-bundle section
requires:
  - slice: S02
    provides: OciSandboxRuntime adapter, SandboxSpec dataclass, ImageRef contracts, preferred_backend routing
  - slice: S03
    provides: build_egress_plan(), EgressRule, NetworkPolicyPlan, compile_squid_acl(), egress topology infrastructure
affects:
  - S05
key_files:
  - src/scc_cli/core/destination_registry.py
  - src/scc_cli/ports/models.py
  - src/scc_cli/application/start_session.py
  - src/scc_cli/adapters/oci_sandbox_runtime.py
  - src/scc_cli/application/launch/preflight.py
  - src/scc_cli/doctor/checks/environment.py
  - src/scc_cli/application/support_bundle.py
  - tests/test_destination_registry.py
  - tests/test_oci_egress_integration.py
  - tests/test_launch_preflight.py
  - tests/test_doctor_checks.py
  - tests/test_support_bundle.py
key_decisions:
  - Registry uses plain dict[str, DestinationSet] for trivial extensibility — no framework, just a typed mapping
  - destination_sets_to_allow_rules helper co-located in registry module to keep rule generation reusable across backends
  - TYPE_CHECKING guard for DestinationSet import in models.py avoids circular dependency while preserving type safety
  - Destination resolution in _build_sandbox_spec only for OCI backend — Desktop sandbox has its own network isolation
  - Enforced-mode preflight wraps resolve ValueError into LaunchPolicyBlockedError for clear user-facing error
  - Runtime probe in doctor accessed via bootstrap.get_default_adapters() not direct adapter import, respecting import boundary enforcement
  - Effective egress support-bundle section uses independent try/except per subsection so partial data survives failures
patterns_established:
  - Provider destination set → SandboxSpec → egress plan threading pattern: registry resolves names, spec carries typed sets, adapter converts to allow rules
  - Preflight validation pattern for enforced-mode launches: resolve destination sets before launch, fail closed on unknown sets
  - Doctor check pattern for runtime-dependent probes: access via bootstrap, return warning on failure, never crash
  - Support-bundle resilience pattern: independent try/except per data source so partial diagnostics survive subsystem failures
observability_surfaces:
  - scc doctor 'Runtime Backend' check — reports preferred_backend, display_name, version
  - scc support bundle 'effective_egress' section — runtime_backend, network_policy, resolved_destination_sets
drill_down_paths:
  - .gsd/milestones/M003/slices/S04/tasks/T01-SUMMARY.md
  - .gsd/milestones/M003/slices/S04/tasks/T02-SUMMARY.md
  - .gsd/milestones/M003/slices/S04/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-04T10:42:06.827Z
blocker_discovered: false
---

# S04: Policy integration, provider destination validation, and operator diagnostics

**Provider destination sets are resolved from a typed registry, threaded through SandboxSpec into the OCI adapter's egress plan, validated at preflight for enforced mode, and visible in doctor/support-bundle diagnostics.**

## What Happened

S04 delivered the end-to-end wiring from provider destination metadata through to operator-visible diagnostics, completing the policy integration layer for M003's enforced web egress.

**T01 — Provider Destination Registry** created `src/scc_cli/core/destination_registry.py`, a pure module mapping named destination set IDs (`anthropic-core`, `openai-core`) to typed `DestinationSet` objects with concrete provider hostnames. It exposes `PROVIDER_DESTINATION_SETS`, `resolve_destination_sets(names)` (raises ValueError for unknowns), and `destination_sets_to_allow_rules(sets)` which converts resolved sets to `EgressRule` allow tuples. 17 unit tests cover registry contents, resolution (happy path, ordering, empty, errors), and rule generation (single/multi host, combined sets, target matching, type checks, reason format).

**T02 — SandboxSpec threading and preflight validation** added a `destination_sets` field to the frozen `SandboxSpec` dataclass, wired `_build_sandbox_spec()` to resolve provider destinations via the registry for OCI backends, threaded destination-derived allow rules into `build_egress_plan()` in OciSandboxRuntime, and extended `evaluate_launch_preflight()` with enforced-mode destination resolvability validation. A `TYPE_CHECKING` guard avoids circular imports for DestinationSet in models.py. 7 new tests cover destination-aware egress plan construction and enforced-mode preflight edge cases.

**T03 — Doctor check and support-bundle diagnostics** added `check_runtime_backend()` to the doctor checks module, probing the Docker runtime via `bootstrap.get_default_adapters().runtime_probe` (respecting the import boundary). It reports `preferred_backend`, `display_name`, and version, returning a pass/warning CheckResult. The `effective_egress` section in `build_support_bundle_manifest()` includes `runtime_backend` (from probe), `network_policy` (from user config), and `resolved_destination_sets` (from registry). Each subsection uses independent try/except so partial data survives probe failures. 6 new tests cover doctor check variants and support-bundle resilience.

All three tasks passed targeted tests, mypy, and ruff check. The full suite grew from 3402 to 3432 tests (30 net new), all passing.

## Verification

Slice-level verification ran all three gate checks:

1. **Targeted tests** — `uv run pytest --rootdir "$PWD" tests/test_destination_registry.py tests/test_oci_egress_integration.py tests/test_launch_preflight.py tests/test_doctor_checks.py tests/test_support_bundle.py -q` → 107 passed
2. **Type check** — `uv run mypy src/scc_cli` → Success: no issues found in 249 source files
3. **Lint** — `uv run ruff check` → All checks passed
4. **Full regression** — `uv run pytest --rootdir "$PWD" -q` → 3432 passed, 23 skipped, 4 xfailed (30 net new tests from S04)

## Requirements Advanced

- R001 — Three new modules follow clean architecture patterns: pure destination registry in core, SandboxSpec threading respects frozen dataclass contracts, doctor checks respect import boundary guardrail, support-bundle uses application-owned path. 30 new tests maintain coverage discipline.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

T02 used a TYPE_CHECKING guard for DestinationSet import in models.py to avoid circular dependency — architecturally sound, minor deviation from plan which didn't anticipate the cycle. T03 used bootstrap.get_default_adapters() instead of direct adapter import for the runtime probe — cleaner than the plan's suggestion and respects the import boundary guardrail.

## Known Limitations

Destination registry is currently hardcoded with anthropic-core and openai-core. Future providers require a code change to extend the registry. This is intentional for V1 — a config-driven registry is deferred until the provider set grows.

## Follow-ups

S05 should verify that doctor and support-bundle outputs match the diagnostic surface requirements in D015 (active team context, effective destination sets, runtime backend, network mode, blocked reasons). S05 should also verify docs truthfulness against the actual enforcement model.

## Files Created/Modified

- `src/scc_cli/core/destination_registry.py` — New module: provider destination set registry with resolve and rule-generation helpers
- `src/scc_cli/ports/models.py` — Added destination_sets field to frozen SandboxSpec dataclass
- `src/scc_cli/application/start_session.py` — Wired destination resolution into _build_sandbox_spec for OCI backends
- `src/scc_cli/adapters/oci_sandbox_runtime.py` — Threaded destination-derived allow rules into build_egress_plan()
- `src/scc_cli/application/launch/preflight.py` — Added enforced-mode preflight validation for unresolvable destination sets
- `src/scc_cli/doctor/checks/environment.py` — Added check_runtime_backend() doctor check
- `src/scc_cli/doctor/checks/__init__.py` — Wired check_runtime_backend into run_all_checks()
- `src/scc_cli/doctor/__init__.py` — Added check_runtime_backend to package exports
- `src/scc_cli/doctor/core.py` — Added check_runtime_backend to run_doctor()
- `src/scc_cli/application/support_bundle.py` — Added effective_egress section to support bundle manifest
- `tests/test_destination_registry.py` — 17 tests for destination registry resolution and rule generation
- `tests/test_oci_egress_integration.py` — Extended with destination-aware egress plan tests
- `tests/test_launch_preflight.py` — Extended with enforced-mode destination validation tests
- `tests/test_doctor_checks.py` — 4 tests for check_runtime_backend doctor check
- `tests/test_support_bundle.py` — 2 tests for effective_egress support bundle section
