---
estimated_steps: 19
estimated_files: 7
skills_used: []
---

# T02: Wire destination sets through SandboxSpec to OCI adapter and extend preflight validation

Thread resolved destination sets from the application layer through SandboxSpec into the OCI adapter's `build_egress_plan()` call, and extend preflight to validate enforced-mode destination resolvability.

Steps:
1. Add `destination_sets: tuple[DestinationSet, ...] = ()` field to `SandboxSpec` in `src/scc_cli/ports/models.py`. Import `DestinationSet` from `scc_cli.core.contracts`. Since SandboxSpec is `@dataclass(frozen=True)` and the new field has a default, all existing construction sites are safe.
2. Update `_build_sandbox_spec()` in `src/scc_cli/application/start_session.py`:
   - Add `agent_provider: AgentProvider | None = None` parameter.
   - If `agent_provider` is not None and `runtime_info.preferred_backend == "oci"`, call `agent_provider.capability_profile()` to get `required_destination_set`, then call `resolve_destination_sets((required_destination_set,))` from the registry.
   - Pass resolved sets as `destination_sets=resolved_sets` to `SandboxSpec()`.
   - Update the caller in `prepare_start_session()` to pass `agent_provider=dependencies.agent_provider`.
3. Update `OciSandboxRuntime.run()` in `src/scc_cli/adapters/oci_sandbox_runtime.py`:
   - In the `WEB_EGRESS_ENFORCED` branch, call `destination_sets_to_allow_rules(spec.destination_sets)` to generate allow rules.
   - Pass both `destination_sets=spec.destination_sets` and `egress_rules=allow_rules` to `build_egress_plan()`.
   - Import `destination_sets_to_allow_rules` from `scc_cli.core.destination_registry`.
4. Extend `evaluate_launch_preflight()` in `src/scc_cli/application/launch/preflight.py`:
   - After the existing locked-down-web check, add an enforced-mode check: if `network_policy == NetworkPolicy.WEB_EGRESS_ENFORCED.value` and `required_destination_sets` is non-empty, call `resolve_destination_sets()` wrapped in try/except ValueError → raise `LaunchPolicyBlockedError` with a clear message about unresolvable sets.
5. Write/extend tests:
   - Extend `tests/test_oci_egress_integration.py` with tests verifying that destination sets on SandboxSpec produce allow rules in the egress plan and ACL output.
   - Extend `tests/test_launch_preflight.py` with tests for enforced-mode unresolvable destination sets.
   - Run `tests/test_start_session_image_routing.py` to confirm no regression.
6. Verify: `uv run pytest --rootdir "$PWD" tests/test_oci_egress_integration.py tests/test_launch_preflight.py tests/test_start_session_image_routing.py -q` passes, `uv run mypy src/scc_cli` clean.

## Inputs

- ``src/scc_cli/core/destination_registry.py` — resolve_destination_sets() and destination_sets_to_allow_rules() from T01`
- ``src/scc_cli/core/contracts.py` — DestinationSet, EgressRule dataclasses`
- ``src/scc_cli/ports/models.py` — SandboxSpec to extend`
- ``src/scc_cli/application/start_session.py` — _build_sandbox_spec() to wire`
- ``src/scc_cli/adapters/oci_sandbox_runtime.py` — run() to integrate`
- ``src/scc_cli/application/launch/preflight.py` — evaluate_launch_preflight() to extend`

## Expected Output

- ``src/scc_cli/ports/models.py` — SandboxSpec with destination_sets field`
- ``src/scc_cli/application/start_session.py` — _build_sandbox_spec() resolves provider destinations`
- ``src/scc_cli/adapters/oci_sandbox_runtime.py` — run() passes destination-derived allow rules to build_egress_plan()`
- ``src/scc_cli/application/launch/preflight.py` — enforced-mode destination validation`
- ``tests/test_oci_egress_integration.py` — new tests for destination-aware egress plan construction`
- ``tests/test_launch_preflight.py` — new tests for enforced-mode unresolvable destinations`

## Verification

uv run pytest --rootdir "$PWD" tests/test_oci_egress_integration.py tests/test_launch_preflight.py tests/test_start_session_image_routing.py tests/test_egress_policy.py -q && uv run mypy src/scc_cli
