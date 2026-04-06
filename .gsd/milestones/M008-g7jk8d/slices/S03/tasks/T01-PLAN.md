---
estimated_steps: 14
estimated_files: 2
skills_used: []
---

# T01: Guard workspace preference and conflict-path consistency, test ask+last-used preselection

**Failed launch guard:**
1. Verify set_workspace_last_used_provider() is called ONLY after finalize_launch() succeeds in all five sites (via preflight module from S01). If finalize_launch raises, the preference must NOT be written.
2. Verify the KEEP_EXISTING conflict path also writes workspace preference consistently across flow.py start(), run_start_wizard_flow(), dashboard _handle_worktree_start(), and dashboard _handle_session_resume(). All four should behave the same.

**Ask + workspace_last_used preselection:**
3. Test: global preference='ask', workspace_last_used='codex' → chooser appears (ask suppresses auto-select), BUT codex is preselected as default.
4. Verify _resolve_prompt_default() in provider_choice.py correctly returns workspace_last_used when it's in connected_allowed and candidates.
5. Test: global preference='ask', workspace_last_used='codex', codex NOT connected → chooser appears, no preselection.
6. Test: global preference='ask', no workspace_last_used → chooser appears with no preselection.

**Write edge case tests:**
- Failed launch (finalize_launch raises) → workspace preference NOT updated
- Cancelled launch → workspace preference NOT updated
- Successful launch → workspace preference written
- KEEP_EXISTING via start → preference written
- KEEP_EXISTING via dashboard resume → preference written (same behavior)

## Inputs

- `src/scc_cli/commands/launch/preflight.py`
- `src/scc_cli/commands/launch/provider_choice.py`
- `src/scc_cli/workspace_local_config.py`

## Expected Output

- `tests/test_workspace_provider_persistence.py`

## Verification

uv run pytest tests/test_workspace_provider_persistence.py tests/test_start_provider_choice.py -v
