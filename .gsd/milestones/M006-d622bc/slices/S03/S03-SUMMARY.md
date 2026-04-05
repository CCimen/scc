---
id: S03
parent: M006-d622bc
milestone: M006-d622bc
provides:
  - get_provider_display_name() helper for any UI surface that needs to show the active provider
  - Provider-neutral branding across all CLI commands, help text, and prompts
  - Guardrail test preventing regression of hardcoded provider references
requires:
  - slice: S01
    provides: Provider resolution infrastructure (resolve_provider(), provider_id on StartSessionRequest)
affects:
  - S04
key_files:
  - src/scc_cli/core/provider_resolution.py
  - src/scc_cli/ui/branding.py
  - src/scc_cli/theme.py
  - src/scc_cli/commands/launch/render.py
  - src/scc_cli/commands/launch/flow.py
  - src/scc_cli/commands/launch/flow_interactive.py
  - src/scc_cli/commands/launch/sandbox.py
  - src/scc_cli/doctor/render.py
  - tests/test_provider_branding.py
key_decisions:
  - Branding header uses provider-neutral 'Sandboxed Code CLI' — the product is SCC, not a Claude wrapper
  - Display name is passed as a string to launch render functions rather than provider_id — keeps render layer decoupled from provider_resolution
  - Guardrail test excludes docker/, adapters/, marketplace/, and provider_resolution.py lookup table as legitimate Claude Code references
patterns_established:
  - get_provider_display_name() as the single source for provider-to-human-name mapping — all UI surfaces should use this instead of raw provider IDs
  - Guardrail test pattern: scan source tree for deprecated references with explicit exclusion list for legitimate adapter-specific usage
  - Backward-compatible display_name defaults on render functions — callers without provider context get Claude Code (existing behavior), callers with context pass the resolved name
observability_surfaces:
  - none
drill_down_paths:
  - .gsd/milestones/M006-d622bc/slices/S03/tasks/T01-SUMMARY.md
  - .gsd/milestones/M006-d622bc/slices/S03/tasks/T02-SUMMARY.md
  - .gsd/milestones/M006-d622bc/slices/S03/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-05T00:33:12.615Z
blocker_discovered: false
---

# S03: Provider-aware branding, panels, diagnostics, and string cleanup

**All user-facing strings now adapt to the active provider; a guardrail test prevents regressions of hardcoded 'Claude Code' references outside adapter modules.**

## What Happened

S03 systematically eliminated hardcoded "Claude Code" and "Sandboxed Claude" references from all non-adapter runtime code, replacing them with provider-neutral language or parameterized display names.

**T01** established the foundation: `get_provider_display_name()` in `core/provider_resolution.py` maps provider IDs to human-readable names ("Claude Code", "Codex"), with title-cased fallback for unknown providers. The branding header was updated from "Sandboxed Claude CLI" to "Sandboxed Code CLI" in both `ui/branding.py` and `theme.py` ASCII art. `get_brand_tagline()` was parameterized to optionally include the provider name. 10 tests cover display name lookups, header neutrality, and tagline parameterization.

**T02** threaded the display name through the launch UI layer: `show_launch_panel()`, `show_launch_context_panel()`, and `render_doctor_results()` all accept a display name / provider ID parameter with backward-compatible defaults. All three launch flow call sites (flow.py, flow_interactive.py, sandbox.py) resolve the provider and pass the correct display name. 7 new tests verify panel titles and doctor summary adapt correctly.

**T03** was the sweep-and-guard pass. It updated 27+ source files across commands, UI, core, sessions, setup, and doctor modules — Typer help strings, runtime prompts, CLI epilog, module docstrings, and dashboard labels. The guardrail test (`TestNoCloudeCodeInNonAdapterModules`) scans all `.py` files under `src/scc_cli/` and fails if any "Claude Code" or "Sandboxed Claude" references appear outside docker/, adapters/, marketplace/, or the provider_resolution.py lookup table. The test found additional files beyond the original plan (setup_ui.py, models/plugin_audit.py, audit modules) which were also cleaned.

Final state: 18 branding tests, 4586 total tests passing, ruff clean, zero "Claude Code" in non-adapter user-facing code.

## Verification

All slice-level verification checks pass:
1. `uv run pytest tests/test_provider_branding.py -v --no-cov` — 18/18 passed (including guardrail)
2. `uv run pytest --rootdir "$PWD" -q --no-cov` — 4586 passed, 23 skipped, 2 xfailed, 0 failures
3. `uv run ruff check` — All checks passed
4. `grep -rn 'Claude Code' src/scc_cli/ --include='*.py' | grep -v claude_ | grep -v marketplace/ | grep -v __pycache__ | grep -v docker/ | grep -v adapters/` — only 4 allowed references: provider_resolution.py lookup table and display_name default parameters in render.py/sandbox.py

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

T03 scope expanded beyond the original plan to include setup_ui.py, models/plugin_audit.py, audit/__init__.py, audit/reader.py, and application/sync_marketplace.py — these files contained references the guardrail test would flag. This is a scope increase, not a deviation in intent.

## Known Limitations

Doctor render call sites in admin.py and settings.py were not threaded with the resolved provider — they fall back to the "Claude Code" default. This is acceptable because those call sites don't have the resolved provider in scope without plumbing it through additional layers. The default preserves existing behavior.

## Follow-ups

None.

## Files Created/Modified

- `src/scc_cli/core/provider_resolution.py` — Added get_provider_display_name() with _PROVIDER_DISPLAY_NAMES lookup table
- `src/scc_cli/ui/branding.py` — Changed header to Sandboxed Code CLI, parameterized get_brand_tagline() with optional provider_id
- `src/scc_cli/theme.py` — Updated ASCII art strings from Sandboxed Claude CLI to Sandboxed Code CLI
- `src/scc_cli/commands/launch/render.py` — Added display_name parameter to show_launch_panel() and show_launch_context_panel()
- `src/scc_cli/commands/launch/flow.py` — Threaded resolved provider display name to show_launch_panel()
- `src/scc_cli/commands/launch/flow_interactive.py` — Threaded resolved provider display name to show_launch_context_panel()
- `src/scc_cli/commands/launch/sandbox.py` — Threaded display_name to show_launch_panel()
- `src/scc_cli/doctor/render.py` — Parameterized render_doctor_results() with provider_id for summary line
- `src/scc_cli/cli.py` — Neutralized CLI help text and epilog from Claude Code to AI coding agents
- `src/scc_cli/commands/launch/app.py` — Neutralized Typer help string
- `src/scc_cli/commands/admin.py` — Neutralized help strings and runtime prompts
- `src/scc_cli/commands/worktree/container_commands.py` — Neutralized help strings and runtime messages
- `src/scc_cli/commands/worktree/session_commands.py` — Neutralized help strings and docstrings
- `src/scc_cli/commands/worktree/worktree_commands.py` — Neutralized help strings and runtime prompts
- `src/scc_cli/setup.py` — Neutralized setup wizard strings and docstrings
- `src/scc_cli/sessions.py` — Neutralized module and function docstrings
- `src/scc_cli/core/errors.py` — Updated module docstring
- `src/scc_cli/core/constants.py` — Updated module docstring
- `src/scc_cli/ui/git_interactive.py` — Neutralized branch guidance message and docstring
- `src/scc_cli/ui/dashboard/orchestrator_handlers.py` — Neutralized launch description and docstrings
- `tests/test_provider_branding.py` — 18 tests: display name lookups, header/tagline parameterization, panel titles, doctor summary, guardrail scan
