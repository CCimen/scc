---
id: S01
parent: M004
milestone: M004
provides:
  - SafetyEngine protocol port (ports/safety_engine.py)
  - DefaultSafetyEngine implementation (core/safety_engine.py)
  - Shell tokenizer in core (core/shell_tokenizer.py)
  - Git safety rules with typed verdicts (core/git_safety_rules.py)
  - Network tool rules with typed verdicts (core/network_tool_rules.py)
  - CommandFamily enum (core/enums.py)
  - FakeSafetyEngine for downstream tests (tests/fakes/fake_safety_engine.py)
  - safety_engine field wired in DefaultAdapters via bootstrap
requires:
  []
affects:
  - S02
  - S03
key_files:
  - src/scc_cli/core/enums.py
  - src/scc_cli/core/shell_tokenizer.py
  - src/scc_cli/core/git_safety_rules.py
  - src/scc_cli/core/network_tool_rules.py
  - src/scc_cli/core/safety_engine.py
  - src/scc_cli/ports/safety_engine.py
  - src/scc_cli/bootstrap.py
  - tests/test_shell_tokenizer.py
  - tests/test_git_safety_rules.py
  - tests/test_network_tool_rules.py
  - tests/test_safety_engine.py
  - tests/test_safety_engine_boundary.py
  - tests/fakes/fake_safety_engine.py
  - tests/fakes/__init__.py
key_decisions:
  - D016: Keep SafetyPolicy.rules as dict[str, Any] with standalone _matched_rule_to_policy_key() mapping and policy.rules.get(key, True) for fail-closed semantics
  - Copied shell tokenizer verbatim from plugin to preserve battle-tested parsing logic
  - Used _block() helper + _RULE_NAMES dict to centralize verdict construction in git_safety_rules
  - Used PurePosixPath for network tool path stripping to avoid filesystem access
  - safety_engine field is Optional on DefaultAdapters to avoid breaking existing consumers
patterns_established:
  - Lift-from-plugin pattern: copy module verbatim, adapt return types to typed contracts, re-run adapted plugin tests as characterization tests
  - Safety rule module shape: pure function analyze_X(tokens) -> SafetyVerdict | None, no side effects, no I/O
  - Engine orchestration: tokenize → route by command family → check rules → apply policy overrides (disable/warn) → fail-closed on missing keys
  - FakeSafetyEngine pattern: configurable verdict + call recording list for downstream test inspection
  - Boundary guardrail for core safety: AST-scan test prevents plugin/provider imports from leaking into core safety modules
observability_surfaces:
  - none
drill_down_paths:
  - .gsd/milestones/M004/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M004/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M004/slices/S01/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-04T11:50:49.514Z
blocker_discovered: false
---

# S01: Shared safety policy and verdict engine

**Delivered a provider-neutral safety engine with shell tokenizer, git safety rules, and network tool rules — all lifted from the plugin into core with typed SafetyVerdict returns, orchestrated by DefaultSafetyEngine with fail-closed semantics, and wired into bootstrap.**

## What Happened

S01 established the foundational safety evaluation layer for M004. The work proceeded in three tasks that built cleanly on each other.

**T01 — Foundation layer.** Extended `core/enums.py` with the `CommandFamily` enum (DESTRUCTIVE_GIT, NETWORK_TOOL). Lifted the shell tokenizer from the scc-safety-net plugin into `core/shell_tokenizer.py` — a pure-stdlib module with 5 public functions (split_commands, tokenize, strip_wrappers, extract_bash_c, extract_all_commands). Defined the `SafetyEngine` protocol port with a single `evaluate(command, policy) -> SafetyVerdict` method. Adapted all 44 plugin shell tests to the new import path; all passed unchanged, confirming behavioral equivalence.

**T02 — Rule modules.** Lifted all git safety analyzers from the plugin's `git_rules.py` (494 lines) into `core/git_safety_rules.py`, adapting every `analyze_*` function to return `SafetyVerdict | None` instead of raw strings. Introduced a `_block()` helper and `_RULE_NAMES` dict to centralize verdict construction. Created `core/network_tool_rules.py` as a new V1 module detecting 6 network tools (curl, wget, ssh, scp, sftp, rsync) with typed verdicts and PurePosixPath-based path stripping. Adapted the plugin's 105 git rule tests and wrote 22 new network tool tests — 127 total, all passing.

**T03 — Engine orchestration and bootstrap wiring.** Implemented `DefaultSafetyEngine` which tokenizes commands via `extract_all_commands`, routes git-prefixed tokens through `analyze_git`, routes all tokens through `analyze_network_tool`, then applies policy overrides (rule disabling via `policy.rules`, warn mode with WARNING prefix). Missing policy keys default to True (fail-closed semantics per D009). Wired the engine into `DefaultAdapters` in bootstrap with `safety_engine: SafetyEngine | None = None`. Created `FakeSafetyEngine` with configurable verdict and call recording for downstream tests. Added `safety_engine` to `build_fake_adapters()`. Wrote 21 integration tests covering block, allow, warn, disabled rules, nested bash -c commands, shell operators, pipe chaining, and protocol conformance. Added a boundary guardrail test (AST-scan) that prevents plugin/provider imports in core safety modules.

All 193 slice-specific tests and the full suite of 3630 tests pass. mypy (254 files) and ruff are clean.

## Verification

All three verification gates pass:
- `uv run mypy src/scc_cli` → Success: no issues found in 254 source files
- `uv run ruff check` → All checks passed
- `uv run pytest tests/test_shell_tokenizer.py tests/test_git_safety_rules.py tests/test_network_tool_rules.py tests/test_safety_engine.py tests/test_safety_engine_boundary.py -v` → 193 passed
- `uv run pytest --rootdir "$PWD" -q` → 3630 passed, 23 skipped, 4 xfailed (zero failures)

## Requirements Advanced

- R001 — Safety logic lifted from plugin monolith into focused core modules (shell_tokenizer, git_safety_rules, network_tool_rules, safety_engine) — each independently testable with clear single-purpose APIs. Bootstrap wiring follows established Optional-field pattern for safe extension.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

Minor deviations from plan, none material:
- T02: Changed `analyzers` dict type from `dict[str, object]` to `dict[str, Callable[[list[str]], SafetyVerdict | None]]` to satisfy mypy without `type: ignore`.
- T02: Used `PurePosixPath` for network tool path stripping to avoid filesystem access.
- T03: Fixed a pre-existing ruff I001 import sorting issue in tests/test_git_safety_rules.py from T02.

## Known Limitations

None. The engine covers the exact scope defined in D009 (destructive git + explicit network tools). Rule coverage matches the plugin's full analyzer set.

## Follow-ups

None.

## Files Created/Modified

- `src/scc_cli/core/enums.py` — Added CommandFamily enum with DESTRUCTIVE_GIT and NETWORK_TOOL members
- `src/scc_cli/core/shell_tokenizer.py` — New — shell tokenizer lifted from plugin with 5 public functions (split_commands, tokenize, strip_wrappers, extract_bash_c, extract_all_commands)
- `src/scc_cli/core/git_safety_rules.py` — New — all git safety analyzers from plugin adapted to return SafetyVerdict | None
- `src/scc_cli/core/network_tool_rules.py` — New — V1 network tool detection for 6 tools (curl, wget, ssh, scp, sftp, rsync)
- `src/scc_cli/core/safety_engine.py` — New — DefaultSafetyEngine orchestrating tokenizer + git rules + network rules with fail-closed policy
- `src/scc_cli/ports/safety_engine.py` — New — SafetyEngine Protocol with evaluate(command, policy) -> SafetyVerdict
- `src/scc_cli/bootstrap.py` — Added safety_engine field to DefaultAdapters, wired DefaultSafetyEngine in get_default_adapters()
- `tests/test_shell_tokenizer.py` — New — 44 tests adapted from plugin test suite for shell tokenizer
- `tests/test_git_safety_rules.py` — New — 105 tests adapted from plugin test suite for git safety rules
- `tests/test_network_tool_rules.py` — New — 22 tests for network tool detection covering all tools, negatives, path-qualified binaries
- `tests/test_safety_engine.py` — New — 21 integration tests for DefaultSafetyEngine covering block/allow/warn/disable/nesting/protocol
- `tests/test_safety_engine_boundary.py` — New — AST-scan boundary guardrail preventing plugin/provider imports in core safety modules
- `tests/fakes/fake_safety_engine.py` — New — FakeSafetyEngine with configurable verdict and call recording
- `tests/fakes/__init__.py` — Added safety_engine=FakeSafetyEngine() to build_fake_adapters()
