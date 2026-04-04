# S04 — Research: Fail-closed policy loading, audit surfaces, and operator diagnostics

**Date:** 2026-04-04

## Summary

S04 bridges the gap between the existing raw policy-injection code in `docker/launch.py` (dict-based, container-focused), the new typed safety engine/adapter layer from S01–S03, and the operator-facing diagnostics that don't yet exist for the safety domain. Today there are three disconnected surfaces: (1) `docker/launch.py` has `get_effective_safety_net_policy()` returning untyped `dict[str, Any]` for container mount, (2) `core/safety_engine.py` and the provider adapters accept typed `SafetyPolicy` objects, and (3) the standalone evaluator `scc_safety_eval/policy.py` loads policy from `SCC_POLICY_PATH` env var inside the container. The operator has no way to inspect what safety policy is active, see recent safety verdicts, or diagnose policy-loading failures from the host side.

The work is medium-complexity and follows established patterns. The policy-loading logic (`docker/launch.py`) needs a small typed bridge to produce `SafetyPolicy` from org config dicts. The audit surface follows the same pattern as `read_launch_audit_diagnostics()` — a bounded reader over the existing JSONL sink, filtered to `safety.check` events. Doctor gets a new safety-policy check following the `CheckResult` pattern. Support-bundle gets a `safety` section. All patterns already exist; S04 applies them to the safety domain.

Primary recommendation: decompose into three tasks — (T01) host-side typed policy loader + doctor check, (T02) safety audit reader + CLI surface + support-bundle integration, (T03) integration tests and guardrails.

## Recommendation

**Approach: Typed policy loader + audit reader + diagnostics, all following existing patterns.**

1. **Host-side policy loader** — Add `core/safety_policy_loader.py` with a `load_safety_policy(org_config: dict[str, Any] | None) -> SafetyPolicy` function. This reuses the extraction/validation logic from `docker/launch.py` but returns a typed `SafetyPolicy` instead of raw dict. The existing `docker/launch.py` functions stay untouched (they're used by the container-mount path which needs raw dicts). Fail-closed: any parse error → default `SafetyPolicy(action="block")`.

2. **Doctor check** — Add `doctor/checks/safety.py` with `check_safety_policy()` returning `CheckResult`. It probes: can org config be loaded? Does it contain `security.safety_net`? Is the action valid? Are there unknown rule keys? This goes through `bootstrap.get_default_adapters()` per the KNOWLEDGE.md rule.

3. **Safety audit reader** — Add `application/safety_audit.py` with a `read_safety_audit_diagnostics()` function. Pattern: reuse the existing `read_launch_audit_diagnostics()` from `application/launch/audit_log.py`, filtering to `event_type == "safety.check"`. Return a `SafetyAuditDiagnostics` dataclass with recent blocked/allowed counts, last blocked command, and recent events.

4. **CLI surface** — Add `scc support safety-audit` command under the existing `support_app` typer. Human and `--json` modes. Uses the same `_render_` pattern as `support_launch_audit_cmd`.

5. **Support-bundle integration** — Add a `safety` section to `build_support_bundle_manifest()` containing the effective policy summary and recent safety audit events.

## Implementation Landscape

### Key Files

- `src/scc_cli/core/safety_policy_loader.py` — **New.** Host-side typed policy loader: `load_safety_policy(org_config) -> SafetyPolicy`. Reuses validation logic (valid actions, fail-closed defaults) without importing from `docker/launch.py`.
- `src/scc_cli/doctor/checks/safety.py` — **New.** `check_safety_policy() -> CheckResult`. Probes org config availability and policy validity.
- `src/scc_cli/doctor/checks/__init__.py` — **Modify.** Register the new safety check in `run_all_checks()` and `__all__`.
- `src/scc_cli/doctor/core.py` — **Modify.** Wire `check_safety_policy()` into `run_doctor()`.
- `src/scc_cli/application/safety_audit.py` — **New.** `SafetyAuditDiagnostics` dataclass + `read_safety_audit_diagnostics()` bounded reader over the JSONL sink filtered to `safety.check` events.
- `src/scc_cli/commands/support.py` — **Modify.** Add `scc support safety-audit` command.
- `src/scc_cli/presentation/json/safety_audit_json.py` — **New.** JSON envelope builder for safety audit diagnostics.
- `src/scc_cli/kinds.py` — **Modify.** Add `SAFETY_AUDIT = "SafetyAudit"` kind.
- `src/scc_cli/application/support_bundle.py` — **Modify.** Add `safety` section to manifest with effective policy + recent safety events.
- `src/scc_cli/adapters/local_audit_event_sink.py` — No changes needed; it already writes all AuditEvents including safety.check events.
- `src/scc_cli/bootstrap.py` — No changes needed; safety adapters already wired from S03.
- `tests/test_safety_policy_loader.py` — **New.** Tests for typed policy loader (fail-closed, valid actions, extraction from nested org config).
- `tests/test_safety_audit.py` — **New.** Tests for safety audit reader (filtering, bounded scan, empty sink, malformed lines).
- `tests/test_safety_doctor_check.py` — **New.** Tests for doctor safety-policy check.

### Build Order

**T01: Host-side typed policy loader + doctor check** — Riskiest because it introduces the new `safety_policy_loader.py` module. Build the loader first, then the doctor check. The loader is independently testable with no dependencies on the JSONL sink or CLI. Doctor check follows the established `CheckResult` pattern exactly.

**T02: Safety audit reader + CLI surface + support-bundle integration** — Depends on T01 for the effective policy summary in the support bundle. The reader is a thin filter over the existing `_tail_lines` / JSONL parsing infrastructure. The CLI surface follows the exact pattern of `support_launch_audit_cmd`.

**T03: Integration tests and guardrails** — End-to-end verification that the full chain works: org config → typed policy → engine evaluation → audit event → safety audit reader → diagnostics. Also adds a guardrail test that `safety_policy_loader.py` never imports from `docker/launch.py` (preventing circular dependency).

### Verification Approach

1. **Policy loader tests**: `uv run pytest tests/test_safety_policy_loader.py -v` — fail-closed defaults, valid action passthrough, invalid action → block, nested extraction, missing security key, non-dict org config.
2. **Doctor check tests**: `uv run pytest tests/test_safety_doctor_check.py -v` — passed when policy loads, warning when no org config, error on malformed.
3. **Safety audit tests**: `uv run pytest tests/test_safety_audit.py -v` — filtering to safety.check events, bounded scan, blocked/allowed counts, empty sink.
4. **Ruff clean**: `uv run ruff check`
5. **Mypy clean**: `uv run mypy src/scc_cli`
6. **Full regression**: `uv run pytest --rootdir "$PWD" -q` — must exceed 3773 baseline.

## Constraints

- `docker/launch.py` functions must not be modified — they serve the container-mount path and have 30+ existing tests. The new `safety_policy_loader.py` must be independent.
- The safety audit reader reads the same JSONL file as `read_launch_audit_diagnostics()` — it must not introduce a parallel persistence format (per KNOWLEDGE.md: "add a bounded redaction-safe reader over the canonical sink").
- Doctor checks that need adapter access must go through `bootstrap.get_default_adapters()` (per KNOWLEDGE.md guardrail).
- Policy loader must be fail-closed: any parse failure → `SafetyPolicy(action="block")`. Never fail-open.

## Common Pitfalls

- **Importing from docker/launch.py** — The validation logic in `get_effective_safety_net_policy()` is tempting to reuse, but it returns `dict[str, Any]` and importing it into core would create a core→docker dependency. Duplicate the small validation (action in {"block","warn","allow"}, default to "block") in the new loader. It's ~10 lines.
- **JSONL filtering performance** — The safety audit reader must use the same bounded tail-read pattern as `read_launch_audit_diagnostics()`, not scan the entire file. The sink file grows unboundedly.
- **Missing `| None = None` defaults** — If any new field is added to `DefaultAdapters` or `SupportBundleDependencies`, it must have a `None` default to avoid breaking existing construction sites.
