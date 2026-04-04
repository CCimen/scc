---
estimated_steps: 67
estimated_files: 10
skills_used: []
---

# T01: Create standalone safety evaluator package with contract tests

---
estimated_steps: 5
estimated_files: 10
skills_used: []
---

# T01: Create standalone safety evaluator package with contract tests

**Slice:** S02 — Runtime wrapper baseline in scc-base
**Milestone:** M004

## Description

Create the standalone Python evaluator package at `images/scc-base/wrappers/scc_safety_eval/` that embeds the safety logic from S01's core modules. The evaluator must produce identical verdicts to `DefaultSafetyEngine` for the same inputs, using only Python 3 stdlib (no scc_cli dependency). Write contract tests that feed identical inputs to both `DefaultSafetyEngine` and the standalone evaluator and assert identical results.

The evaluator package contains adapted copies of 4 core modules (shell_tokenizer, git_safety_rules, network_tool_rules, contracts/enums combined) plus new files: engine.py (orchestrator), policy.py (policy loader from SCC_POLICY_PATH), and __main__.py (CLI entry point).

All `scc_cli.core.*` imports must be replaced with relative imports within the package. Only `SafetyPolicy`, `SafetyVerdict` from contracts and `CommandFamily` from enums are needed.

## Steps

1. Create `images/scc-base/wrappers/scc_safety_eval/__init__.py` (empty package marker).

2. Create `images/scc-base/wrappers/scc_safety_eval/contracts.py` — stripped-down version containing only `SafetyPolicy` and `SafetyVerdict` dataclasses. Remove all other types (DestinationSet, EgressRule, etc.). Remove the `from .enums import NetworkPolicy, SeverityLevel` import. Keep `from dataclasses import dataclass, field` and `from typing import Any`.

3. Create `images/scc-base/wrappers/scc_safety_eval/enums.py` — stripped-down version containing only `CommandFamily(str, Enum)`. Remove all other enums.

4. Create `images/scc-base/wrappers/scc_safety_eval/shell_tokenizer.py` — copy of `src/scc_cli/core/shell_tokenizer.py` verbatim (no scc_cli imports in this file — it only uses stdlib).

5. Create `images/scc-base/wrappers/scc_safety_eval/git_safety_rules.py` — copy of `src/scc_cli/core/git_safety_rules.py` with imports changed from `from scc_cli.core.contracts import SafetyVerdict` to `from .contracts import SafetyVerdict` and `from scc_cli.core.enums import CommandFamily` to `from .enums import CommandFamily`.

6. Create `images/scc-base/wrappers/scc_safety_eval/network_tool_rules.py` — copy of `src/scc_cli/core/network_tool_rules.py` with imports changed from `from scc_cli.core.contracts import SafetyVerdict` to `from .contracts import SafetyVerdict` and `from scc_cli.core.enums import CommandFamily` to `from .enums import CommandFamily`.

7. Create `images/scc-base/wrappers/scc_safety_eval/engine.py` — adapted version of `src/scc_cli/core/safety_engine.py` with all `scc_cli.core.*` imports replaced by relative imports (`.contracts`, `.git_safety_rules`, `.network_tool_rules`, `.shell_tokenizer`). Keep the `DefaultSafetyEngine` class and all logic identical.

8. Create `images/scc-base/wrappers/scc_safety_eval/policy.py` — policy loader that reads `$SCC_POLICY_PATH` environment variable. If unset or file missing, return a fail-closed default policy (`SafetyPolicy(action='block', rules={})`). If file exists, parse JSON and construct `SafetyPolicy`. Handle malformed JSON by returning the fail-closed default (never fail-open).

9. Create `images/scc-base/wrappers/scc_safety_eval/__main__.py` — CLI entry point:
   - Usage: `python3 -m scc_safety_eval <tool> [args...]`
   - Load policy via `policy.py`
   - Reconstruct the command string from sys.argv (tool name + args)
   - Evaluate using the engine
   - Exit 0 if allowed, exit 2 with reason on stderr if blocked
   - Handle any unexpected exceptions by exiting 2 (fail-closed)

10. Write `tests/test_safety_eval_contract.py` — contract tests that:
    - Import both `DefaultSafetyEngine` from `scc_cli.core.safety_engine` and the standalone engine from `scc_safety_eval.engine`
    - Feed identical command/policy pairs to both engines
    - Assert `verdict.allowed`, `verdict.matched_rule`, and `verdict.command_family` match for each pair
    - Test cases: force push blocked, network tool blocked, safe command allowed, warn mode, disabled rule, nested bash -c, empty command, allow policy bypass
    - Add `images/scc-base/wrappers` to sys.path in the test file so the standalone package is importable

## Must-Haves

- [ ] All 8 package files exist under `images/scc-base/wrappers/scc_safety_eval/`
- [ ] Zero `scc_cli` imports in the evaluator package — only stdlib and relative imports
- [ ] Policy loader returns fail-closed default when SCC_POLICY_PATH is unset, file missing, or JSON malformed
- [ ] CLI entry point exits 0 for allowed, 2 for blocked, 2 for unexpected errors
- [ ] Contract tests pass proving verdict equivalence with DefaultSafetyEngine

## Verification

```bash
# Verify no scc_cli imports in evaluator package
grep -r 'scc_cli' images/scc-base/wrappers/scc_safety_eval/ && echo FAIL || echo PASS

# Contract tests
uv run pytest tests/test_safety_eval_contract.py -v

# Existing tests still pass
uv run pytest --rootdir "$PWD" -q
```

## Inputs

- `src/scc_cli/core/shell_tokenizer.py` — source module to copy verbatim
- `src/scc_cli/core/git_safety_rules.py` — source module to adapt imports
- `src/scc_cli/core/network_tool_rules.py` — source module to adapt imports
- `src/scc_cli/core/safety_engine.py` — source module to adapt imports
- `src/scc_cli/core/contracts.py` — source for SafetyPolicy and SafetyVerdict extraction
- `src/scc_cli/core/enums.py` — source for CommandFamily extraction

## Expected Output

- `images/scc-base/wrappers/scc_safety_eval/__init__.py` — package marker
- `images/scc-base/wrappers/scc_safety_eval/contracts.py` — stripped SafetyPolicy + SafetyVerdict
- `images/scc-base/wrappers/scc_safety_eval/enums.py` — stripped CommandFamily enum
- `images/scc-base/wrappers/scc_safety_eval/shell_tokenizer.py` — verbatim copy
- `images/scc-base/wrappers/scc_safety_eval/git_safety_rules.py` — adapted imports
- `images/scc-base/wrappers/scc_safety_eval/network_tool_rules.py` — adapted imports
- `images/scc-base/wrappers/scc_safety_eval/engine.py` — adapted orchestrator
- `images/scc-base/wrappers/scc_safety_eval/policy.py` — policy loader
- `images/scc-base/wrappers/scc_safety_eval/__main__.py` — CLI entry point
- `tests/test_safety_eval_contract.py` — contract tests

## Inputs

- `src/scc_cli/core/shell_tokenizer.py`
- `src/scc_cli/core/git_safety_rules.py`
- `src/scc_cli/core/network_tool_rules.py`
- `src/scc_cli/core/safety_engine.py`
- `src/scc_cli/core/contracts.py`
- `src/scc_cli/core/enums.py`

## Expected Output

- `images/scc-base/wrappers/scc_safety_eval/__init__.py`
- `images/scc-base/wrappers/scc_safety_eval/contracts.py`
- `images/scc-base/wrappers/scc_safety_eval/enums.py`
- `images/scc-base/wrappers/scc_safety_eval/shell_tokenizer.py`
- `images/scc-base/wrappers/scc_safety_eval/git_safety_rules.py`
- `images/scc-base/wrappers/scc_safety_eval/network_tool_rules.py`
- `images/scc-base/wrappers/scc_safety_eval/engine.py`
- `images/scc-base/wrappers/scc_safety_eval/policy.py`
- `images/scc-base/wrappers/scc_safety_eval/__main__.py`
- `tests/test_safety_eval_contract.py`

## Verification

grep -r 'scc_cli' images/scc-base/wrappers/scc_safety_eval/ && exit 1 || true; uv run pytest tests/test_safety_eval_contract.py -v; uv run pytest --rootdir "$PWD" -q
