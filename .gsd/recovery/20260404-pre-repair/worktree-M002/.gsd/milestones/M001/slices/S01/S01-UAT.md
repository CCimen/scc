# S01: Baseline truth and implementation-root freeze — UAT

**Milestone:** M001
**Written:** 2026-04-03T15:20:53.650Z

# UAT

1. Confirm the active working directory and git toplevel are both `scc-sync-1.7.3`.
2. Review `.gsd/milestones/M001/M001-ROADMAP.md` and `.gsd/milestones/M001/slices/S01/S01-PLAN.md` to see the structured M001 execution plan.
3. Review the task summaries under `.gsd/milestones/M001/slices/S01/tasks/` for the inventory and baseline verification evidence.
4. Run the fixed gate manually if desired:
   - `uv run ruff check`
   - `uv run mypy src/scc_cli`
   - `uv run pytest`
5. Confirm the gate is green and that legacy network-policy terms are still present for S02 to migrate, rather than silently disappearing without recorded work.

