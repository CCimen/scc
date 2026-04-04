# S01 Research: Shared Safety Policy and Verdict Engine

## Summary

S01 introduces the core safety engine — the typed, provider-neutral, fail-closed evaluation surface that both providers (Claude and Codex) consume. This is **targeted research**: the pattern is well-understood (port/adapter with pure evaluation core), the relevant code already exists in two locations (plugin `scc_safety_impl` and core `contracts.py` stubs), and the main work is lifting, normalizing, and wiring into a new `SafetyEngine` protocol.

## Recommendation

Build the safety engine in three layers inside `src/scc_cli/`:

1. **Core models** — extend `core/contracts.py` with `CommandFamily` enum and `SafetyRule` dataclass; refine existing `SafetyPolicy` and `SafetyVerdict`.
2. **Pure evaluation logic** — new `core/safety_engine.py` with a `SafetyEngine` protocol and a `DefaultSafetyEngine` implementation that lifts `git_rules.py` and `shell.py` from the plugin into provider-neutral core.
3. **Policy loading port** — new `ports/safety_policy_loader.py` protocol + adapter stub so policy resolution is injected, not hardcoded.

Do NOT import from `sandboxed-code-plugins/scc-safety-net/` — copy and adapt the pure logic. The plugin remains as a Claude-native integration surface in later slices.

## Implementation Landscape

### What Already Exists

| Component | Location | Notes |
|---|---|---|
| `SafetyPolicy` dataclass | `src/scc_cli/core/contracts.py:101-113` | Frozen; has `action`, `rules: dict[str, Any]`, `source`. Already M001 shape. |
| `SafetyVerdict` dataclass | `src/scc_cli/core/contracts.py:116-129` | Frozen; has `allowed`, `reason`, `matched_rule`, `command_family`. Already target shape. |
| `AuditEvent` dataclass | `src/scc_cli/core/contracts.py:132-152` | Shared audit record used by M002 launch audit and M003 egress. Reusable for safety events. |
| `SafetyNetConfig` schema model | `src/scc_cli/marketplace/schema.py:212-225` | Pydantic model for org config `security.safety_net` blob. Defines the config shape. |
| Plugin `git_rules.py` | `sandboxed-code-plugins/scc-safety-net/scripts/scc_safety_impl/git_rules.py` (415 lines) | Complete destructive git analysis — `analyze_git(tokens) -> str|None`. Pure logic, zero imports outside stdlib. |
| Plugin `shell.py` | `sandboxed-code-plugins/scc-safety-net/scripts/scc_safety_impl/shell.py` (183 lines) | Shell tokenization, bash -c nesting, wrapper stripping. Pure logic, zero imports outside stdlib. |
| Plugin `policy.py` | `sandboxed-code-plugins/scc-safety-net/scripts/scc_safety_impl/policy.py` (330 lines) | Policy loading from env/workspace/cache, validation, SCC-managed mode detection, fail-safe defaults. |
| Plugin `hook.py` | `sandboxed-code-plugins/scc-safety-net/scripts/scc_safety_impl/hook.py` (137 lines) | Orchestrator: `analyze_command(cmd) -> str|None`. Maps subcommands to policy rules, checks policy enablement. |
| Plugin test suite | `sandboxed-code-plugins/scc-safety-net/tests/test_git_rules.py`, `test_shell.py`, `test_policy.py`, `test_hook.py` | Comprehensive unit tests. Can be adapted for the new core engine. |
| `evaluation/` layer | `src/scc_cli/evaluation/` (4 files, 399 lines) | Existing exception/override system for plugins/MCP. Different domain (config evaluation, not command safety). Not directly reusable but shows the pure-function pattern the project already follows. |
| `AuditEventSink` port + adapter | `src/scc_cli/ports/audit_event_sink.py`, `src/scc_cli/adapters/local_audit_event_sink.py` | Working JSONL audit sink from M002/S04. Safety verdicts can emit `AuditEvent` through this sink. |
| `DefaultAdapters` composition root | `src/scc_cli/bootstrap.py` | Single place to wire the new engine. Already holds `audit_event_sink`. |
| Fakes directory | `tests/fakes/` | Established pattern for test doubles. Need a `FakeSafetyEngine` here. |
| `core/enums.py` | `src/scc_cli/core/enums.py` | Centralized enums. `CommandFamily` enum belongs here. |

### What Does NOT Exist Yet

| Gap | Where it goes | Notes |
|---|---|---|
| `SafetyEngine` protocol | `src/scc_cli/ports/safety_engine.py` | New port. `evaluate(command: str, policy: SafetyPolicy) -> SafetyVerdict`. |
| `DefaultSafetyEngine` | `src/scc_cli/core/safety_engine.py` | Pure engine: tokenize → classify → check rules → produce verdict. |
| `CommandFamily` enum | `src/scc_cli/core/enums.py` | `DESTRUCTIVE_GIT`, `NETWORK_TOOL` (V1 families per D-009, spec 05). |
| `SafetyRule` typed model | `src/scc_cli/core/contracts.py` | Individual rule with `id`, `command_family`, `enabled`, `description`. Replaces `dict[str, Any]` rule flags. |
| Shell tokenization in core | `src/scc_cli/core/shell_tokenizer.py` | Lift from plugin `shell.py`. Pure, zero-dependency. |
| Git analysis in core | `src/scc_cli/core/git_safety_rules.py` | Lift from plugin `git_rules.py`. Pure, zero-dependency. Returns typed verdicts instead of raw strings. |
| Network tool analysis in core | `src/scc_cli/core/network_tool_rules.py` | New. V1: `curl`, `wget`, `ssh`, `scp`, `sftp`, `rsync` with remote target. Simpler than git rules — mostly presence-based matching. |
| Policy normalization helper | Inside `core/safety_engine.py` or a small `core/safety_policy_loader.py` | Convert `SafetyNetConfig`/dict → typed `SafetyPolicy`. Fail-closed on bad input. |
| Bootstrap wiring | `src/scc_cli/bootstrap.py` | Add `safety_engine: SafetyEngine` to `DefaultAdapters`. |
| `FakeSafetyEngine` | `tests/fakes/fake_safety_engine.py` | Programmable fake for downstream tests. |
| Engine unit tests | `tests/test_safety_engine.py` | Core evaluation tests. Adapt from plugin test suite. |
| Git rule unit tests | `tests/test_git_safety_rules.py` | Lift and adapt from plugin `test_git_rules.py`. |
| Network tool tests | `tests/test_network_tool_rules.py` | New. |
| Boundary guardrail | `tests/test_architecture_invariants.py` (extend) or new `tests/test_safety_engine_boundary.py` | Ensure no direct plugin imports leak into core. |

### Architecture Seams — Natural Task Boundaries

1. **Core models & enums** (`CommandFamily` enum, `SafetyRule` dataclass) — small, independent, unblocks everything.
2. **Shell tokenizer lift** (`core/shell_tokenizer.py`) — pure copy-adapt from plugin, zero coupling.
3. **Git safety rules lift** (`core/git_safety_rules.py`) — pure copy-adapt, returns typed `SafetyVerdict` instead of string.
4. **Network tool rules** (`core/network_tool_rules.py`) — new, small. Pattern follows git rules.
5. **SafetyEngine protocol + DefaultSafetyEngine** (`ports/safety_engine.py`, `core/safety_engine.py`) — orchestrates the above pieces.
6. **Bootstrap + fake wiring** — integrate into composition root, add test fake.
7. **Comprehensive tests** — engine + rules + boundary guardrails.

Tasks 1-4 are independent once models exist. Task 5 depends on 2-4. Task 6 depends on 5. Task 7 spans all.

### Key Design Constraints

- **Fail-closed** (Constitution §9, spec 05, D015): If policy cannot be loaded or parsed, the engine MUST block. `SafetyPolicy` default action is already `"block"`. The engine must check and enforce this invariant.
- **Provider-neutral** (Constitution §6): The engine lives in `core/` and `ports/`. No Claude or Codex imports. Provider adapters consume the engine in S03.
- **Typed verdicts** (Constitution §7): Current plugin returns raw strings (`"BLOCKED: Force push destroys remote history."`). The engine must return `SafetyVerdict(allowed=False, reason="...", matched_rule="git.force_push", command_family="destructive-git")`.
- **Audit integration** (D006, existing infrastructure): Verdicts should produce `AuditEvent` records. The engine itself doesn't write to audit — that's the caller's job (S02 wrappers, S03 adapters). But the engine should provide a `to_audit_event()` helper on `SafetyVerdict` or a mapping helper.
- **Per-rule enablement** (existing plugin pattern): Each rule (e.g. `block_force_push`) can be individually enabled/disabled via policy. The typed `SafetyRule` model should carry an `enabled` field, and `SafetyPolicy.rules` should move from `dict[str, Any]` to something more typed — either `dict[str, bool]` for V1 or `tuple[SafetyRule, ...]`.
- **V1 scope** (D-009, spec 05): Only `destructive-git` and `network-tool` families. No package managers, no cloud CLIs.
- **Network tools are defense-in-depth** (D014, D015): In enforced-egress modes, topology+proxy are the hard control. Network tool wrappers add better denial UX and audit, not the actual enforcement boundary.

### Risk Assessment

| Risk | Severity | Mitigation |
|---|---|---|
| `SafetyPolicy.rules` is `dict[str, Any]` — changing it to a stricter type would break existing test code | Medium | Keep `dict[str, Any]` as the parse/compat layer; add a normalization step that produces a typed internal representation. Or add `SafetyRule` alongside without breaking the existing frozen dataclass. |
| Plugin git_rules tests are extensive — adapting them takes time | Low | The logic is identical; change return types from `str|None` to `SafetyVerdict` and update assertions. Mostly mechanical. |
| Network tool rules are new (no existing implementation) | Medium | V1 scope is simple: detect the binary name (`curl`, `wget`, `ssh`, etc.) in tokens after wrapper stripping. No deep argument analysis needed for V1 — presence of the tool in a sandboxed context is the safety signal. |
| `SafetyPolicy` is frozen — can't add methods to it | Low | Use standalone helper functions (`normalize_policy()`, `is_rule_enabled()`) instead of methods. Consistent with existing patterns. |

### SafetyPolicy Rules Typing Decision

The current `SafetyPolicy.rules` is `dict[str, Any]`. Changing to `dict[str, bool]` would be a frozen-dataclass-compatible narrowing. Alternatively, introduce a parallel `SafetyRuleSet` model that the engine normalizes into from the raw dict. The planner should decide — either approach works. The key constraint: the `SafetyPolicy` dataclass is already used in `test_core_contracts.py` and must remain frozen.

### Existing Test Patterns to Follow

- `tests/fakes/fake_agent_provider.py` — pattern for `FakeSafetyEngine`
- `tests/test_core_contracts.py` — pattern for testing frozen dataclasses and protocol conformance
- `tests/test_architecture_invariants.py` — pattern for boundary guardrail assertions
- Plugin `tests/test_git_rules.py` — 80+ test cases covering all git subcommand analyzers, to be adapted

### Verification Strategy

```bash
# Type checking
uv run mypy src/scc_cli

# Lint
uv run ruff check

# All tests (including new safety engine tests)
uv run pytest --rootdir "$PWD" -q

# Targeted new tests
uv run pytest tests/test_safety_engine.py tests/test_git_safety_rules.py tests/test_network_tool_rules.py -v
```

### Files Likely Touched (Summary)

**New files:**
- `src/scc_cli/core/safety_engine.py` — DefaultSafetyEngine
- `src/scc_cli/core/shell_tokenizer.py` — lifted from plugin
- `src/scc_cli/core/git_safety_rules.py` — lifted from plugin, typed returns
- `src/scc_cli/core/network_tool_rules.py` — new V1 network tool matching
- `src/scc_cli/ports/safety_engine.py` — SafetyEngine protocol
- `tests/fakes/fake_safety_engine.py` — test double
- `tests/test_safety_engine.py` — engine tests
- `tests/test_git_safety_rules.py` — git rule tests
- `tests/test_network_tool_rules.py` — network tool tests

**Modified files:**
- `src/scc_cli/core/enums.py` — add `CommandFamily` enum
- `src/scc_cli/core/contracts.py` — optionally add `SafetyRule` model
- `src/scc_cli/bootstrap.py` — wire `safety_engine` into `DefaultAdapters`
- `tests/test_architecture_invariants.py` — add safety boundary guardrail (optional, could be separate file)

### Skill Discovery

No external skills are needed. The work is pure Python with stdlib + dataclasses. The existing codebase patterns (ports/adapters, frozen dataclasses, pure evaluation functions, pytest fixtures) are well-established and sufficient.
