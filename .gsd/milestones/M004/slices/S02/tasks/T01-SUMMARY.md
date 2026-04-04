---
id: T01
parent: S02
milestone: M004
key_files:
  - images/scc-base/wrappers/scc_safety_eval/engine.py
  - images/scc-base/wrappers/scc_safety_eval/policy.py
  - images/scc-base/wrappers/scc_safety_eval/__main__.py
  - images/scc-base/wrappers/scc_safety_eval/contracts.py
  - images/scc-base/wrappers/scc_safety_eval/enums.py
  - images/scc-base/wrappers/scc_safety_eval/shell_tokenizer.py
  - images/scc-base/wrappers/scc_safety_eval/git_safety_rules.py
  - images/scc-base/wrappers/scc_safety_eval/network_tool_rules.py
  - tests/test_safety_eval_contract.py
key_decisions:
  - Stripped contracts.py to only SafetyPolicy+SafetyVerdict and enums.py to only CommandFamily for minimal runtime surface
  - Policy loader prints warning to stderr on load failure but returns fail-closed default (never fail-open)
duration: 
verification_result: passed
completed_at: 2026-04-04T12:17:33.837Z
blocker_discovered: false
---

# T01: Created standalone scc_safety_eval package (9 files, stdlib-only) with 28 contract tests proving identical verdicts to DefaultSafetyEngine

**Created standalone scc_safety_eval package (9 files, stdlib-only) with 28 contract tests proving identical verdicts to DefaultSafetyEngine**

## What Happened

Created the images/scc-base/wrappers/scc_safety_eval/ package with 9 files adapted from the host CLI's core modules. The package uses only Python 3 stdlib and relative imports — zero scc_cli references. Files: __init__.py, contracts.py (SafetyPolicy+SafetyVerdict), enums.py (CommandFamily), shell_tokenizer.py (verbatim copy), git_safety_rules.py, network_tool_rules.py, engine.py (all with relative imports), policy.py (fail-closed loader from SCC_POLICY_PATH), __main__.py (CLI: exit 0 allowed, exit 2 blocked/error). Wrote 28 contract tests covering force push, mirror, refspec, network tools, safe commands, warn mode, allow bypass, disabled rules, nested bash -c, empty commands, and more.

## Verification

All three slice-level verification checks pass: (1) grep -r scc_cli finds zero matches in evaluator package, (2) 28/28 contract tests pass proving field-level verdict equivalence, (3) full suite 3658 passed. Manual CLI verification confirmed exit codes: blocked→2, allowed→0, no-args→2, missing policy→fail-closed block.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `grep -r 'scc_cli' images/scc-base/wrappers/scc_safety_eval/ && echo FAIL || echo PASS` | 0 | ✅ pass | 100ms |
| 2 | `uv run pytest tests/test_safety_eval_contract.py -v` | 0 | ✅ pass | 740ms |
| 3 | `uv run pytest --rootdir "$PWD" -q` | 0 | ✅ pass | 43010ms |

## Deviations

Removed scc_cli references from docstring comments in contracts.py and enums.py to pass the grep verification check — logic unchanged.

## Known Issues

None.

## Files Created/Modified

- `images/scc-base/wrappers/scc_safety_eval/engine.py`
- `images/scc-base/wrappers/scc_safety_eval/policy.py`
- `images/scc-base/wrappers/scc_safety_eval/__main__.py`
- `images/scc-base/wrappers/scc_safety_eval/contracts.py`
- `images/scc-base/wrappers/scc_safety_eval/enums.py`
- `images/scc-base/wrappers/scc_safety_eval/shell_tokenizer.py`
- `images/scc-base/wrappers/scc_safety_eval/git_safety_rules.py`
- `images/scc-base/wrappers/scc_safety_eval/network_tool_rules.py`
- `tests/test_safety_eval_contract.py`
