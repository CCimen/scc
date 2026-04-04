---
estimated_steps: 4
estimated_files: 2
skills_used: []
---

# T04: Integration tests and full verification

1. Add cross-provider integration tests to test_render_pipeline_integration.py verifying portable artifacts render on both providers.
2. Update test_docs_truthfulness.py if the D023 comment in bundle_resolver.py needs updating.
3. Run full test suite, ruff, mypy.
4. Verify no regressions.

## Inputs

- `tests/test_render_pipeline_integration.py`
- `src/scc_cli/core/bundle_resolver.py`

## Expected Output

- `tests/test_render_pipeline_integration.py with portable artifact integration tests`

## Verification

uv run pytest --rootdir "$PWD" -q && uv run ruff check && uv run mypy src/scc_cli
