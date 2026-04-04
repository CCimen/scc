# S04: Typed control-plane contracts and shared error-audit seams — UAT

**Milestone:** M001
**Written:** 2026-04-03T15:47:50.872Z

# UAT

1. Review the new typed seam files:
   - `src/scc_cli/core/contracts.py`
   - `src/scc_cli/ports/agent_provider.py`
2. Review the aligned error/output seam files:
   - `src/scc_cli/core/errors.py`
   - `src/scc_cli/core/error_mapping.py`
   - `src/scc_cli/json_command.py`
3. Confirm the JSON error payload now exposes `error_category` and `exit_code` while keeping the envelope shape stable.
4. Review the new tests:
   - `tests/test_core_contracts.py`
   - `tests/test_error_mapping.py`
   - `tests/test_json_command.py`
5. Run the fixed gate:
   - `uv run ruff check`
   - `uv run mypy src/scc_cli`
   - `uv run pytest`
6. Confirm the gate is green and that the typed seams and aligned error metadata are present.

