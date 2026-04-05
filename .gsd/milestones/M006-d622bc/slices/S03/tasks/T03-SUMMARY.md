---
id: T03
parent: S03
milestone: M006-d622bc
key_files:
  - tests/test_provider_branding.py
  - src/scc_cli/cli.py
  - src/scc_cli/commands/launch/app.py
  - src/scc_cli/commands/admin.py
  - src/scc_cli/commands/worktree/session_commands.py
  - src/scc_cli/commands/worktree/container_commands.py
  - src/scc_cli/commands/worktree/worktree_commands.py
  - src/scc_cli/setup.py
  - src/scc_cli/ui/git_interactive.py
  - src/scc_cli/ui/dashboard/orchestrator_handlers.py
  - src/scc_cli/sessions.py
key_decisions:
  - Guardrail test excludes docker/, adapters/, marketplace/ dirs plus provider_resolution.py and display_name default params as allowed Claude Code references
duration: 
verification_result: passed
completed_at: 2026-04-05T00:28:34.890Z
blocker_discovered: false
---

# T03: Swept all 'Claude Code' and 'Sandboxed Claude' references from non-adapter modules to provider-neutral language and added guardrail test

**Swept all 'Claude Code' and 'Sandboxed Claude' references from non-adapter modules to provider-neutral language and added guardrail test**

## What Happened

Systematically replaced all "Claude Code" and "Sandboxed Claude" references in 27 non-adapter source files with provider-neutral language ("agent", "AI coding agents", "Sandboxed Code CLI"). Updated Typer help strings, runtime prompts, CLI epilog, and module docstrings across commands, UI, core, sessions, setup, and doctor modules. Added a guardrail test (TestNoCloudeCodeInNonAdapterModules) that scans all .py files for regressions, with proper exclusions for docker/, adapters/, marketplace/, provider_resolution.py lookup table, and display_name default parameters.

## Verification

- uv run pytest tests/test_provider_branding.py -v — 18 passed including guardrail
- uv run pytest --rootdir "$PWD" -q — 4586 passed, 23 skipped, 2 xfailed, 0 failures
- uv run ruff check — all checks passed
- uv run mypy on core files — clean
- grep verification confirms only allowed adapter references remain

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_provider_branding.py -v` | 0 | ✅ pass | 1630ms |
| 2 | `uv run pytest --rootdir "$PWD" -q` | 0 | ✅ pass | 72740ms |
| 3 | `uv run ruff check` | 0 | ✅ pass | 5300ms |
| 4 | `uv run mypy src/scc_cli/core/provider_resolution.py src/scc_cli/ui/branding.py src/scc_cli/theme.py` | 0 | ✅ pass | 3000ms |

## Deviations

Also swept setup_ui.py, models/plugin_audit.py, audit/__init__.py, audit/reader.py, and application/sync_marketplace.py which were not in the original plan but contained references the guardrail test would flag. Fixed two files corrupted by overly-broad sed patterns during initial editing.

## Known Issues

None.

## Files Created/Modified

- `tests/test_provider_branding.py`
- `src/scc_cli/cli.py`
- `src/scc_cli/commands/launch/app.py`
- `src/scc_cli/commands/admin.py`
- `src/scc_cli/commands/worktree/session_commands.py`
- `src/scc_cli/commands/worktree/container_commands.py`
- `src/scc_cli/commands/worktree/worktree_commands.py`
- `src/scc_cli/setup.py`
- `src/scc_cli/ui/git_interactive.py`
- `src/scc_cli/ui/dashboard/orchestrator_handlers.py`
- `src/scc_cli/sessions.py`
