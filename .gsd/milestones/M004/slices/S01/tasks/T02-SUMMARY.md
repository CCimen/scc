---
id: T02
parent: S01
milestone: M004
key_files:
  - src/scc_cli/core/git_safety_rules.py
  - src/scc_cli/core/network_tool_rules.py
  - tests/test_git_safety_rules.py
  - tests/test_network_tool_rules.py
key_decisions:
  - Used _block() helper + _RULE_NAMES dict to centralize verdict construction and keep analyzers identical to plugin logic
  - Used PurePosixPath for network tool path stripping to avoid filesystem access
  - Typed analyzers dict with Callable to satisfy mypy without type: ignore
duration: 
verification_result: passed
completed_at: 2026-04-04T11:40:36.513Z
blocker_discovered: false
---

# T02: Lifted all git safety analyzers from plugin into core with typed SafetyVerdict returns, and created network tool rules module detecting 6 tools

**Lifted all git safety analyzers from plugin into core with typed SafetyVerdict returns, and created network tool rules module detecting 6 tools**

## What Happened

Created git_safety_rules.py by copying the 494-line plugin module and adapting all analyze_* functions to return SafetyVerdict | None instead of str | None. Introduced a _block() helper and _RULE_NAMES dict to centralize verdict construction. Created network_tool_rules.py as a new V1 module detecting 6 network tools (curl, wget, ssh, scp, sftp, rsync) with typed verdicts. Adapted plugin test suite into 105 git safety tests and wrote 22 new network tool tests. All 171 tests pass, mypy and ruff clean.

## Verification

Ran mypy on both source files (0 issues), ruff check (all passed), pytest on both test files (127 tests passed), and full slice verification across all 5 source files and 3 test files (171 tests passed in 0.95s).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run mypy src/scc_cli/core/git_safety_rules.py src/scc_cli/core/network_tool_rules.py` | 0 | ✅ pass | 15800ms |
| 2 | `uv run ruff check src/scc_cli/core/git_safety_rules.py src/scc_cli/core/network_tool_rules.py` | 0 | ✅ pass | 12000ms |
| 3 | `uv run pytest tests/test_git_safety_rules.py tests/test_network_tool_rules.py -v` | 0 | ✅ pass | 940ms |
| 4 | `uv run mypy src/scc_cli/core/enums.py src/scc_cli/core/shell_tokenizer.py src/scc_cli/ports/safety_engine.py (slice)` | 0 | ✅ pass | 3000ms |
| 5 | `uv run ruff check src/scc_cli/core/enums.py src/scc_cli/core/shell_tokenizer.py src/scc_cli/ports/safety_engine.py (slice)` | 0 | ✅ pass | 1000ms |
| 6 | `uv run pytest tests/test_shell_tokenizer.py -v (slice)` | 0 | ✅ pass | 800ms |

## Deviations

Changed analyzers dict type from dict[str, object] to dict[str, Callable[[list[str]], SafetyVerdict | None]] to satisfy mypy without type: ignore comments.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/core/git_safety_rules.py`
- `src/scc_cli/core/network_tool_rules.py`
- `tests/test_git_safety_rules.py`
- `tests/test_network_tool_rules.py`
