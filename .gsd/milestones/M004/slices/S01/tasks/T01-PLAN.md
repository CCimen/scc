---
estimated_steps: 18
estimated_files: 4
skills_used: []
---

# T01: Core models, shell tokenizer lift, and SafetyEngine protocol

## Description

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

## Inputs

- ``src/scc_cli/core/enums.py` — existing enums module to extend with CommandFamily`
- ``src/scc_cli/core/contracts.py` — SafetyPolicy and SafetyVerdict dataclasses used by the protocol`
- ``/Users/ccimen/dev/sccorj/sandboxed-code-plugins/scc-safety-net/scripts/scc_safety_impl/shell.py` — source for shell tokenizer copy-adapt`
- ``/Users/ccimen/dev/sccorj/sandboxed-code-plugins/scc-safety-net/tests/test_shell.py` — source for test adaptation`

## Expected Output

- ``src/scc_cli/core/enums.py` — extended with CommandFamily enum`
- ``src/scc_cli/core/shell_tokenizer.py` — new shell tokenizer module`
- ``src/scc_cli/ports/safety_engine.py` — new SafetyEngine protocol`
- ``tests/test_shell_tokenizer.py` — new shell tokenizer tests`

## Verification

uv run mypy src/scc_cli/core/enums.py src/scc_cli/core/shell_tokenizer.py src/scc_cli/ports/safety_engine.py && uv run ruff check src/scc_cli/core/enums.py src/scc_cli/core/shell_tokenizer.py src/scc_cli/ports/safety_engine.py && uv run pytest tests/test_shell_tokenizer.py -v
