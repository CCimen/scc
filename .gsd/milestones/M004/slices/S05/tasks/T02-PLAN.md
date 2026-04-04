---
estimated_steps: 11
estimated_files: 1
skills_used: []
---

# T02: Safety truthfulness guardrail tests and full exit gate

Extend tests/test_docs_truthfulness.py with M004-specific guardrail tests:

1. test_readme_mentions_safety_audit_command — verify README contains 'safety-audit' (the new S04 command must be documented)

2. test_readme_describes_core_safety_engine — verify README mentions SCC-owned safety engine / runtime safety as a core feature (not only via plugin). Scan for pattern like 'safety engine' or 'runtime safety' in the README.

3. test_readme_enforcement_scope_mentions_runtime_wrappers — verify the enforcement scope section mentions runtime wrappers and the 7 tool families (git + curl/wget/ssh/scp/sftp/rsync)

4. test_safety_engine_core_files_exist — verify all expected core safety modules exist: safety_engine.py, shell_tokenizer.py, git_safety_rules.py, network_tool_rules.py, safety_policy_loader.py

5. test_safety_adapter_files_exist — verify both provider safety adapters exist: claude_safety_adapter.py, codex_safety_adapter.py

Then run the full exit gate:
- uv run ruff check
- uv run mypy src/scc_cli
- uv run pytest --rootdir "$PWD" -q

Confirm test count ≥ 3795 (3790 baseline + ≥5 new).

## Inputs

- `README.md`
- `src/scc_cli/core/safety_engine.py`
- `src/scc_cli/adapters/claude_safety_adapter.py`
- `src/scc_cli/adapters/codex_safety_adapter.py`

## Expected Output

- `tests/test_docs_truthfulness.py with ≥10 total tests (5 existing + 5 new)`

## Verification

uv run ruff check && uv run mypy src/scc_cli && uv run pytest --rootdir "$PWD" -q
