---
estimated_steps: 5
estimated_files: 3
skills_used: []
---

# T03: Re-enable file-size/complexity guardrails and remove transitional ruff ignores

1. Review tests/test_file_sizes.py and tests/test_function_sizes.py — remove all xfail markers, fix any remaining violations
2. Review pyproject.toml [tool.ruff.lint.per-file-ignores] — remove transitional ignores, document permanent ones
3. Re-run guardrails to confirm they pass
4. Update any modules still above 800 lines if any remain from S02 decomposition drift
5. Verify no new modules exceed the guardrail thresholds

## Inputs

- `pyproject.toml`
- `tests/test_file_sizes.py`
- `tests/test_function_sizes.py`

## Expected Output

- `pyproject.toml (cleaned)`
- `tests/test_file_sizes.py (no xfail)`
- `tests/test_function_sizes.py (no xfail)`

## Verification

uv run ruff check && uv run mypy src/scc_cli && uv run pytest tests/test_file_sizes.py tests/test_function_sizes.py -v && uv run pytest --rootdir "$PWD" -q
