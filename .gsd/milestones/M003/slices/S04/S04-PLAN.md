# S04: Policy integration, provider destination validation, and operator diagnostics

**Goal:** Provider destination sets are resolved from a typed registry, threaded through SandboxSpec into the OCI adapter's egress plan, validated at preflight for enforced mode, and visible in doctor/support-bundle diagnostics.
**Demo:** After this: TBD

## Tasks
- [x] **T01: Added provider destination registry with anthropic-core/openai-core sets, resolve/rule-generation helpers, and 17 unit tests** — Create `src/scc_cli/core/destination_registry.py` — a pure module mapping named destination set IDs (e.g. `"anthropic-core"`, `"openai-core"`) to typed `DestinationSet` objects with concrete provider hostnames. Expose `PROVIDER_DESTINATION_SETS` mapping and `resolve_destination_sets(names)` function. Also expose `destination_sets_to_allow_rules(sets)` helper that converts resolved `DestinationSet` tuples into allow-type `EgressRule` objects — this keeps rule generation reusable across backends.

Steps:
1. Create `src/scc_cli/core/destination_registry.py` with:
   - `PROVIDER_DESTINATION_SETS: dict[str, DestinationSet]` mapping `"anthropic-core"` → `DestinationSet(name="anthropic-core", destinations=("api.anthropic.com",), required=True, description="Anthropic API core access")`, and `"openai-core"` → similar for `api.openai.com`.
   - `resolve_destination_sets(names: tuple[str, ...]) -> tuple[DestinationSet, ...]` that looks up each name in the mapping, returning found sets. Raises `ValueError` for unknown names.
   - `destination_sets_to_allow_rules(sets: tuple[DestinationSet, ...]) -> tuple[EgressRule, ...]` that converts each destination in each set to an `EgressRule(target=host, allow=True, reason=f"provider-core: {set.name}")`.
2. Create `tests/test_destination_registry.py` with tests covering:
   - Known set resolution (anthropic-core, openai-core)
   - Unknown set raises ValueError
   - Empty input returns empty tuple
   - Allow-rule generation produces correct EgressRule objects
   - Rule targets match destination set hosts
   - Multiple sets produce combined rules
3. Verify: `uv run pytest --rootdir "$PWD" tests/test_destination_registry.py -q` passes, `uv run mypy src/scc_cli/core/destination_registry.py` clean.
  - Estimate: 25m
  - Files: src/scc_cli/core/destination_registry.py, tests/test_destination_registry.py
  - Verify: uv run pytest --rootdir "$PWD" tests/test_destination_registry.py -q && uv run mypy src/scc_cli/core/destination_registry.py
- [x] **T02: Wired provider destination sets from SandboxSpec through OCI adapter egress plan and added enforced-mode preflight validation for unresolvable destinations** — Thread resolved destination sets from the application layer through SandboxSpec into the OCI adapter's `build_egress_plan()` call, and extend preflight to validate enforced-mode destination resolvability.

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
  - Estimate: 45m
  - Files: src/scc_cli/ports/models.py, src/scc_cli/application/start_session.py, src/scc_cli/adapters/oci_sandbox_runtime.py, src/scc_cli/application/launch/preflight.py, tests/test_oci_egress_integration.py, tests/test_launch_preflight.py, tests/test_start_session_image_routing.py
  - Verify: uv run pytest --rootdir "$PWD" tests/test_oci_egress_integration.py tests/test_launch_preflight.py tests/test_start_session_image_routing.py tests/test_egress_policy.py -q && uv run mypy src/scc_cli
- [ ] **T03: Add runtime backend doctor check and egress policy support bundle section** — Add operator-facing diagnostics: a doctor check for runtime backend type and a support bundle section for effective egress policy.

Steps:
1. Add `check_runtime_backend()` to `src/scc_cli/doctor/checks/environment.py`:
   - Import `DockerRuntimeProbe` from the adapter layer via bootstrap re-export (or use a lightweight probe).
   - Probe the runtime and report `preferred_backend` (docker-sandbox / oci / unavailable) plus `runtime_id` and version.
   - Return `CheckResult` with name `"Runtime Backend"`, pass=True if daemon is reachable, message showing backend type.
   - Handle probe failures gracefully (return warning, not error).
2. Wire `check_runtime_backend()` into the check infrastructure:
   - Add to `run_all_checks()` in `src/scc_cli/doctor/checks/__init__.py` and to `__all__`.
   - Add to `run_doctor()` in `src/scc_cli/doctor/core.py`.
   - Add to `src/scc_cli/doctor/__init__.py` exports.
3. Add `effective_egress` section to `build_support_bundle_manifest()` in `src/scc_cli/application/support_bundle.py`:
   - Include `runtime_backend` (from probe), `network_policy` (from user config if available), and `resolved_destination_sets` (list of set names the active provider requires).
   - Wrap in try/except so probe failures don't crash bundle generation.
4. Write tests:
   - Add tests to `tests/test_doctor_checks.py` for `check_runtime_backend()` — mock the probe to test docker-sandbox, oci, and unavailable cases.
   - Add test to `tests/test_support_bundle.py` for the new `effective_egress` section.
5. Run full suite: `uv run ruff check && uv run mypy src/scc_cli && uv run pytest --rootdir "$PWD" -q`.
  - Estimate: 35m
  - Files: src/scc_cli/doctor/checks/environment.py, src/scc_cli/doctor/checks/__init__.py, src/scc_cli/doctor/__init__.py, src/scc_cli/doctor/core.py, src/scc_cli/application/support_bundle.py, tests/test_doctor_checks.py, tests/test_support_bundle.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest --rootdir "$PWD" tests/test_doctor_checks.py tests/test_support_bundle.py -q && uv run pytest --rootdir "$PWD" -q
