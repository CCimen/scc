---
estimated_steps: 41
estimated_files: 4
skills_used: []
---

# T02: Lift git safety rules and create network tool rules with typed SafetyVerdict returns

## Description

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

## Inputs

- ``src/scc_cli/core/contracts.py` — SafetyVerdict dataclass for return types`
- ``src/scc_cli/core/enums.py` — CommandFamily enum (added in T01)`
- ``/Users/ccimen/dev/sccorj/sandboxed-code-plugins/scc-safety-net/scripts/scc_safety_impl/git_rules.py` — source for git rules copy-adapt (494 lines)`
- ``/Users/ccimen/dev/sccorj/sandboxed-code-plugins/scc-safety-net/tests/test_git_rules.py` — source for test adaptation (459 lines)`

## Expected Output

- ``src/scc_cli/core/git_safety_rules.py` — lifted and typed git safety analysis`
- ``src/scc_cli/core/network_tool_rules.py` — new V1 network tool detection`
- ``tests/test_git_safety_rules.py` — adapted git safety tests with verdict assertions`
- ``tests/test_network_tool_rules.py` — new network tool rule tests`

## Verification

uv run mypy src/scc_cli/core/git_safety_rules.py src/scc_cli/core/network_tool_rules.py && uv run ruff check src/scc_cli/core/git_safety_rules.py src/scc_cli/core/network_tool_rules.py && uv run pytest tests/test_git_safety_rules.py tests/test_network_tool_rules.py -v
