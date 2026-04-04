---
estimated_steps: 7
estimated_files: 7
skills_used: []
---

# T04: Harden fetch/render/merge/install failure handling with fail-closed semantics

Add explicit error handling to the bundle resolver and both renderers:
1. Bundle resolver: missing bundle ID → clear error with available alternatives; disabled bundle → skip with audit log; invalid artifact reference → fail-closed block
2. Claude renderer: materialization failure → blocked with diagnostic; merge conflict → fail with conflict report; file write failure → blocked
3. Codex renderer: plugin creation failure → blocked; rules/hooks write failure → blocked; merge conflict on single-file surfaces → fail with conflict report
4. Create a RendererError exception hierarchy in core/errors.py
5. Ensure all failure paths produce structured error info suitable for support bundles and doctor checks
6. Add negative tests for each failure path

## Inputs

- `src/scc_cli/core/bundle_resolver.py`
- `src/scc_cli/adapters/claude_renderer.py`
- `src/scc_cli/adapters/codex_renderer.py`

## Expected Output

- `tests/test_bundle_resolver.py (negative tests)`
- `tests/test_claude_renderer.py (failure path tests)`
- `tests/test_codex_renderer.py (failure path tests)`

## Verification

uv run ruff check && uv run mypy src/scc_cli && uv run pytest tests/test_bundle_resolver.py tests/test_claude_renderer.py tests/test_codex_renderer.py -v && uv run pytest --rootdir "$PWD" -q
