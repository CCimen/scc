---
estimated_steps: 58
estimated_files: 6
skills_used: []
---

# T03: DefaultSafetyEngine, bootstrap wiring, FakeSafetyEngine, and boundary guardrails

## Description

Implement the `DefaultSafetyEngine` that orchestrates shell tokenization + git rules + network tool rules into one evaluation call. Wire it into `DefaultAdapters` via bootstrap. Add `FakeSafetyEngine` for downstream tests. Add a boundary guardrail test to prevent plugin imports from leaking into core safety modules.

## Steps

1. Create `src/scc_cli/core/safety_engine.py` with `DefaultSafetyEngine` class implementing the `SafetyEngine` protocol from `ports/safety_engine.py`. Implementation:
   - `evaluate(self, command: str, policy: SafetyPolicy) -> SafetyVerdict` method
   - If `command` is empty/whitespace, return `SafetyVerdict(allowed=True, reason="Empty command")`
   - If `policy.action == "allow"`, return `SafetyVerdict(allowed=True, reason="Policy action is allow")`
   - Use `extract_all_commands(command)` from `core.shell_tokenizer` to get all token lists
   - For each token list, check if first token (path-stripped) is `git` → call `analyze_git(tokens)` from `core.git_safety_rules`
   - For each token list, check against `analyze_network_tool(tokens)` from `core.network_tool_rules`
   - If any rule returns a verdict with `allowed=False`, check policy rule enablement: extract the rule name from `matched_rule` (e.g. `git.force_push` maps to policy key `block_force_push`), check `policy.rules.get(rule_key, True)` — if disabled, skip. If enabled (or key not in policy.rules, defaulting True for fail-closed), return the block verdict.
   - If `policy.action == "warn"`, prefix reason with `"WARNING: "` and set `allowed=True`
   - If no rules matched, return `SafetyVerdict(allowed=True, reason="No safety rules matched")`
   - Add a helper function `_matched_rule_to_policy_key(matched_rule: str) -> str | None` that maps `git.force_push` → `block_force_push`, `git.reset_hard` → `block_reset_hard`, etc. Use the same mapping as the plugin's `SUBCOMMAND_TO_RULE` dict from `hook.py` but keyed by matched_rule instead of subcommand.

2. Wire into bootstrap: Add `safety_engine` field to `DefaultAdapters` dataclass in `src/scc_cli/bootstrap.py`. Type: `SafetyEngine | None = None` (optional initially, like `audit_event_sink`). In `get_default_adapters()`, instantiate `DefaultSafetyEngine()` and pass it. Add imports for `SafetyEngine` from ports and `DefaultSafetyEngine` from core.

3. Create `tests/fakes/fake_safety_engine.py` following the `FakeAgentProvider` pattern:
   - `FakeSafetyEngine` with a configurable `verdict` field (default: allow-all)
   - `evaluate()` returns the configured verdict or records calls for assertion
   - Store calls in a `calls: list[tuple[str, SafetyPolicy]]` for downstream tests to inspect

4. Update `tests/fakes/__init__.py`:
   - Import and use `FakeSafetyEngine`
   - Add `safety_engine=FakeSafetyEngine()` to `build_fake_adapters()`

5. Create `tests/test_safety_engine.py` with engine integration tests:
   - Test empty command returns allowed
   - Test `policy.action == "allow"` bypasses all rules
   - Test destructive git command (e.g. `git push --force`) with default block policy returns block verdict
   - Test destructive git command with rule disabled in policy returns allowed
   - Test warn mode returns allowed=True with WARNING prefix in reason
   - Test network tool (e.g. `curl http://example.com`) returns block verdict
   - Test bash -c nesting: `bash -c 'git push --force'` is detected
   - Test shell operators: `echo foo && git push --force` is detected
   - Test safe git command (e.g. `git push`) returns allowed
   - Test non-git, non-network command returns allowed
   - Test protocol conformance: `DefaultSafetyEngine` satisfies `SafetyEngine` protocol

6. Add boundary guardrail to `tests/test_safety_engine_boundary.py`:
   - AST-scan `src/scc_cli/core/safety_engine.py`, `src/scc_cli/core/shell_tokenizer.py`, `src/scc_cli/core/git_safety_rules.py`, `src/scc_cli/core/network_tool_rules.py`
   - Assert no imports from `scc_safety_impl`, `sandboxed_code_plugins`, or any provider-specific module (`scc_cli.adapters.claude*`, `scc_cli.adapters.codex*`)
   - Follow the existing pattern in `tests/test_architecture_invariants.py`

7. Run full verification: `uv run mypy src/scc_cli`, `uv run ruff check`, `uv run pytest --rootdir "$PWD" -q`

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| shell_tokenizer.tokenize | Returns empty list → command passes through (safe: no tokens = no match) | N/A (pure function) | N/A |
| git_safety_rules.analyze_git | Returns None → command allowed (correct: no match) | N/A | N/A |
| policy.rules dict | Missing keys default to True (fail-closed: rule enabled) | N/A | N/A |

## Must-Haves

- [ ] `DefaultSafetyEngine` implements `SafetyEngine` protocol with fail-closed semantics
- [ ] Bootstrap wires `safety_engine` into `DefaultAdapters`
- [ ] `FakeSafetyEngine` available in `tests/fakes/`
- [ ] `build_fake_adapters()` includes `safety_engine`
- [ ] Engine tests cover: block, allow, warn, disabled rule, nested commands, protocol conformance
- [ ] Boundary guardrail prevents plugin/provider imports in core safety modules
- [ ] `uv run mypy src/scc_cli`, `uv run ruff check`, `uv run pytest --rootdir "$PWD" -q` all pass

## Verification

- `uv run mypy src/scc_cli`
- `uv run ruff check`
- `uv run pytest tests/test_safety_engine.py tests/test_safety_engine_boundary.py -v`
- `uv run pytest --rootdir "$PWD" -q` (full suite)

## Inputs

- ``src/scc_cli/core/shell_tokenizer.py` — shell tokenizer from T01`
- ``src/scc_cli/core/git_safety_rules.py` — git rules from T02`
- ``src/scc_cli/core/network_tool_rules.py` — network tool rules from T02`
- ``src/scc_cli/ports/safety_engine.py` — SafetyEngine protocol from T01`
- ``src/scc_cli/core/contracts.py` — SafetyPolicy and SafetyVerdict`
- ``src/scc_cli/bootstrap.py` — DefaultAdapters to extend`
- ``tests/fakes/__init__.py` — fakes registry to update`
- ``tests/test_architecture_invariants.py` — boundary test pattern to follow`

## Expected Output

- ``src/scc_cli/core/safety_engine.py` — DefaultSafetyEngine implementation`
- ``src/scc_cli/bootstrap.py` — updated with safety_engine wiring`
- ``tests/fakes/fake_safety_engine.py` — new test fake`
- ``tests/fakes/__init__.py` — updated with FakeSafetyEngine`
- ``tests/test_safety_engine.py` — engine integration tests`
- ``tests/test_safety_engine_boundary.py` — boundary guardrail test`

## Verification

uv run mypy src/scc_cli && uv run ruff check && uv run pytest tests/test_safety_engine.py tests/test_safety_engine_boundary.py -v && uv run pytest --rootdir "$PWD" -q
