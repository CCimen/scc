---
id: T03
parent: S01
milestone: M003
key_files:
  - tests/test_runtime_detection_hotspots.py
key_decisions:
  - Used Python tokenizer instead of regex for guardrail source scanning to correctly distinguish code references from string/comment mentions
duration: 
verification_result: passed
completed_at: 2026-04-04T08:41:59.923Z
blocker_discovered: false
---

# T03: Added tokenizer-based guardrail test preventing stale docker.check_docker_available() calls outside the adapter layer, full suite green

**Added tokenizer-based guardrail test preventing stale docker.check_docker_available() calls outside the adapter layer, full suite green**

## What Happened

Created tests/test_runtime_detection_hotspots.py with a tokenize-based scanner that detects code-level references to check_docker_available outside three allowed files (docker/core.py definition, docker/__init__.py re-export, adapters/docker_runtime_probe.py adapter). Used Python's tokenize module instead of regex to correctly distinguish NAME tokens from docstring/comment mentions. Ran full verification: ruff clean, mypy clean, 3286 tests pass.

## Verification

All five verification commands pass: guardrail test (1 passed), slice-level probe+contract tests (15 passed), ruff check (clean), mypy (244 files, no issues), full pytest (3286 passed, 0 failed).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_runtime_detection_hotspots.py -q` | 0 | ✅ pass | 1000ms |
| 2 | `uv run pytest tests/test_runtime_probe.py tests/test_core_contracts.py -q` | 0 | ✅ pass | 1100ms |
| 3 | `uv run ruff check` | 0 | ✅ pass | 65700ms |
| 4 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 61500ms |
| 5 | `uv run pytest --rootdir "$PWD" -q` | 0 | ✅ pass | 52000ms |

## Deviations

Switched from regex-based detection to tokenize-based scanning after initial approach incorrectly flagged a docstring mention in docker_sandbox_runtime.py as a violation.

## Known Issues

None.

## Files Created/Modified

- `tests/test_runtime_detection_hotspots.py`
