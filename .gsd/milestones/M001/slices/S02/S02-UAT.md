# S02: Truthful network vocabulary migration — UAT

**Milestone:** M001
**Written:** 2026-04-03T15:29:15.330Z

# UAT

1. Inspect the live config and schema surfaces:
   - `src/scc_cli/core/enums.py`
   - `src/scc_cli/core/network_policy.py`
   - `src/scc_cli/marketplace/schema.py`
   - `src/scc_cli/schemas/org-v1.schema.json`
2. Confirm the active network-policy names are `open`, `web-egress-enforced`, and `locked-down-web`.
3. Inspect `README.md` and one or more files under `examples/` to confirm the example vocabulary matches the code.
4. Run the fixed gate:
   - `uv run ruff check`
   - `uv run mypy src/scc_cli`
   - `uv run pytest`
5. Confirm the gate is green and that no legacy network-policy values remain in the live code/schema/example/test surfaces targeted by this slice.

