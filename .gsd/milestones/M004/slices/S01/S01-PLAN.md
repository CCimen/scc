# S01: Shared safety policy and verdict engine

**Goal:** Safety decisions are produced by one provider-neutral engine with typed verdicts, consumed by both Claude and Codex adapters downstream.
**Demo:** After this: TBD

## Tasks
- [x] **T01: Added CommandFamily enum, lifted shell tokenizer from plugin into core, and defined SafetyEngine protocol port** — ## Description

Establish the foundation for the safety engine: add the `CommandFamily` enum, lift the shell tokenizer from the plugin into core, and define the `SafetyEngine` protocol port. Everything downstream (git rules, network rules, engine, bootstrap) depends on these pieces.

## Steps

1. Add `CommandFamily` enum to `src/scc_cli/core/enums.py` with members `DESTRUCTIVE_GIT = "destructive-git"` and `NETWORK_TOOL = "network-tool"`. Follow the existing `str, Enum` pattern.

2. Create `src/scc_cli/core/shell_tokenizer.py` by copying and adapting from the plugin at `/Users/ccimen/dev/sccorj/sandboxed-code-plugins/scc-safety-net/scripts/scc_safety_impl/shell.py` (213 lines). The module is pure stdlib (shlex, re). Keep all functions: `split_commands`, `tokenize`, `strip_wrappers`, `extract_bash_c`, `extract_all_commands`. Add `from __future__ import annotations`. Ensure type hints on all functions per project style.

3. Create `src/scc_cli/ports/safety_engine.py` with a `SafetyEngine` Protocol class. Single method: `evaluate(self, command: str, policy: SafetyPolicy) -> SafetyVerdict`. Import `SafetyPolicy` and `SafetyVerdict` from `scc_cli.core.contracts`.

4. Create `tests/test_shell_tokenizer.py` by adapting tests from `/Users/ccimen/dev/sccorj/sandboxed-code-plugins/scc-safety-net/tests/test_shell.py` (206 lines). Change import paths from `scc_safety_impl.shell` to `scc_cli.core.shell_tokenizer`. All existing test cases should pass unchanged since the logic is identical.

5. Run `uv run mypy src/scc_cli/core/enums.py src/scc_cli/core/shell_tokenizer.py src/scc_cli/ports/safety_engine.py` and `uv run ruff check src/scc_cli/core/enums.py src/scc_cli/core/shell_tokenizer.py src/scc_cli/ports/safety_engine.py` to validate.

## Must-Haves

- [ ] `CommandFamily` enum with `DESTRUCTIVE_GIT` and `NETWORK_TOOL` members in `core/enums.py`
- [ ] `shell_tokenizer.py` in core with all 5 public functions from plugin `shell.py`
- [ ] `SafetyEngine` Protocol in `ports/safety_engine.py`
- [ ] Shell tokenizer tests adapted from plugin test suite, all passing
- [ ] mypy and ruff clean on all new files

## Verification

- `uv run mypy src/scc_cli/core/enums.py src/scc_cli/core/shell_tokenizer.py src/scc_cli/ports/safety_engine.py`
- `uv run ruff check src/scc_cli/core/enums.py src/scc_cli/core/shell_tokenizer.py src/scc_cli/ports/safety_engine.py`
- `uv run pytest tests/test_shell_tokenizer.py -v`
  - Estimate: 1h30m
  - Files: src/scc_cli/core/enums.py, src/scc_cli/core/shell_tokenizer.py, src/scc_cli/ports/safety_engine.py, tests/test_shell_tokenizer.py
  - Verify: uv run mypy src/scc_cli/core/enums.py src/scc_cli/core/shell_tokenizer.py src/scc_cli/ports/safety_engine.py && uv run ruff check src/scc_cli/core/enums.py src/scc_cli/core/shell_tokenizer.py src/scc_cli/ports/safety_engine.py && uv run pytest tests/test_shell_tokenizer.py -v
- [x] **T02: Lifted all git safety analyzers from plugin into core with typed SafetyVerdict returns, and created network tool rules module detecting 6 tools** — ## Description

Lift the git safety analysis logic from the plugin into core, adapting it to return typed `SafetyVerdict` objects instead of raw strings. Create a new network tool rules module for V1 network tool detection. Both modules use the shell tokenizer from T01 and produce `SafetyVerdict` objects.

## Steps

1. Create `src/scc_cli/core/git_safety_rules.py` by copying and adapting from `/Users/ccimen/dev/sccorj/sandboxed-code-plugins/scc-safety-net/scripts/scc_safety_impl/git_rules.py` (494 lines). Key changes:
   - Add `from __future__ import annotations`
   - Import `SafetyVerdict` from `scc_cli.core.contracts` and `CommandFamily` from `scc_cli.core.enums`
   - Keep all existing pure functions: `normalize_git_tokens`, `has_force_flag`, `has_force_refspec`, `has_force_with_lease`, and all `analyze_*` functions
   - Change the return type of each `analyze_*` function from `str | None` to `SafetyVerdict | None`
   - Where the plugin returned a raw string like `BLOCK_MESSAGES["force_push"]`, return `SafetyVerdict(allowed=False, reason=BLOCK_MESSAGES["force_push"], matched_rule="git.force_push", command_family=CommandFamily.DESTRUCTIVE_GIT)`
   - The `matched_rule` should follow a `git.<rule_name>` pattern (e.g. `git.force_push`, `git.reset_hard`, `git.branch_force_delete`)
   - Keep `BLOCK_MESSAGES` dict for the human-readable reason strings
   - The main `analyze_git(tokens) -> SafetyVerdict | None` entry point stays, returns typed verdict

2. Create `src/scc_cli/core/network_tool_rules.py` — new V1 network tool matching. Structure:
   - `NETWORK_TOOLS = frozenset({"curl", "wget", "ssh", "scp", "sftp", "rsync"})` — tools that access external network
   - `analyze_network_tool(tokens: list[str]) -> SafetyVerdict | None` — checks if the first token (after path stripping via `Path(tokens[0]).name`) is in `NETWORK_TOOLS`. If yes, return `SafetyVerdict(allowed=False, reason="BLOCKED: {tool} may access external network. ...", matched_rule="network.{tool}", command_family=CommandFamily.NETWORK_TOOL)`. If no, return `None`.
   - This is defense-in-depth (D014, D015) — topology+proxy are the hard control. Network tool wrappers add denial UX and audit.

3. Create `tests/test_git_safety_rules.py` by adapting from `/Users/ccimen/dev/sccorj/sandboxed-code-plugins/scc-safety-net/tests/test_git_rules.py` (459 lines). Key changes:
   - Change imports from `scc_safety_impl.git_rules` to `scc_cli.core.git_safety_rules`
   - Where tests assert `result is not None` and check string content, assert `result.allowed is False` and check `result.reason`, `result.matched_rule`, `result.command_family`
   - Where tests assert `result is None`, keep as-is (None means allowed)
   - Helper function tests (`has_force_flag`, `normalize_git_tokens`, etc.) stay unchanged since those return the same types

4. Create `tests/test_network_tool_rules.py` with tests for:
   - Each tool in `NETWORK_TOOLS` produces a block verdict
   - Non-network commands (e.g. `git`, `ls`, `cat`) return `None`
   - Path-qualified binaries (`/usr/bin/curl`) are detected
   - Empty tokens return `None`
   - Verdict fields are correct (`command_family`, `matched_rule`)

5. Run mypy and ruff on all new files, run all new tests.

## Negative Tests

- **Malformed inputs**: empty token list, single empty string, tokens with only flags
- **Boundary conditions**: bare `git` with no subcommand, unknown git subcommands pass through, network tool names as substrings (e.g. `curling` should NOT match)

## Must-Haves

- [ ] `git_safety_rules.py` with all analyzers returning `SafetyVerdict | None`
- [ ] `network_tool_rules.py` detecting 6 network tools with typed verdicts
- [ ] Adapted git rules tests passing (460+ lines of coverage)
- [ ] Network tool rules tests covering all tools, negative cases, and path-qualified binaries
- [ ] mypy and ruff clean

## Verification

- `uv run mypy src/scc_cli/core/git_safety_rules.py src/scc_cli/core/network_tool_rules.py`
- `uv run ruff check src/scc_cli/core/git_safety_rules.py src/scc_cli/core/network_tool_rules.py`
- `uv run pytest tests/test_git_safety_rules.py tests/test_network_tool_rules.py -v`
  - Estimate: 2h
  - Files: src/scc_cli/core/git_safety_rules.py, src/scc_cli/core/network_tool_rules.py, tests/test_git_safety_rules.py, tests/test_network_tool_rules.py
  - Verify: uv run mypy src/scc_cli/core/git_safety_rules.py src/scc_cli/core/network_tool_rules.py && uv run ruff check src/scc_cli/core/git_safety_rules.py src/scc_cli/core/network_tool_rules.py && uv run pytest tests/test_git_safety_rules.py tests/test_network_tool_rules.py -v
- [x] **T03: Implemented DefaultSafetyEngine orchestrating shell tokenization + git rules + network tool rules with fail-closed policy semantics, wired into bootstrap, with FakeSafetyEngine and boundary guardrail tests** — ## Description

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
  - Estimate: 2h
  - Files: src/scc_cli/core/safety_engine.py, src/scc_cli/bootstrap.py, tests/fakes/fake_safety_engine.py, tests/fakes/__init__.py, tests/test_safety_engine.py, tests/test_safety_engine_boundary.py
  - Verify: uv run mypy src/scc_cli && uv run ruff check && uv run pytest tests/test_safety_engine.py tests/test_safety_engine_boundary.py -v && uv run pytest --rootdir "$PWD" -q
