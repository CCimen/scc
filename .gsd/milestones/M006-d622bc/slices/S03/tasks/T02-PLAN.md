---
estimated_steps: 29
estimated_files: 6
skills_used: []
---

# T02: Parameterize launch panels and doctor summary with provider display name

## Description

Update `show_launch_panel()`, `show_launch_context_panel()`, and `render_doctor_results()` to accept and display the active provider's display name instead of hardcoded "Claude Code". Thread `provider_id` from the launch flow call sites.

## Steps

1. Update `src/scc_cli/commands/launch/render.py`:
   - `show_launch_panel()`: Add `display_name: str = "Claude Code"` parameter. Change Panel title from `"Launching Claude Code"` to `f"Launching {display_name}"`.
   - `show_launch_context_panel()`: Add `display_name: str = "Claude Code"` parameter. Same Panel title change.
2. Thread `display_name` at all 3 call sites:
   - `src/scc_cli/commands/launch/flow.py` line ~373: Import `get_provider_display_name` from `core.provider_resolution`. The `resolved_provider` variable is already in scope (line ~256). Pass `display_name=get_provider_display_name(resolved_provider)` to `show_launch_panel()`.
   - `src/scc_cli/commands/launch/flow_interactive.py` line ~713: The function needs access to the resolved provider. It receives `start_request` which has `provider_id`. Import `get_provider_display_name`, pass `display_name=get_provider_display_name(start_request.provider_id or "claude")`.
   - `src/scc_cli/commands/launch/sandbox.py` line ~142: This function receives `start_request` from its caller. Import and pass the same way.
3. Update `src/scc_cli/doctor/render.py`:
   - `render_doctor_results()`: Add `provider_id: str | None = None` parameter. When `result.all_ok`, use `get_provider_display_name(provider_id or "claude")` in the summary line: `"Ready to run {display_name}."`
4. Find the doctor render call site and thread `provider_id` if easily accessible. If not, the default ("claude") preserves current behavior.
5. Write tests in `tests/test_provider_branding.py` (extend T01's file):
   - `show_launch_panel()` with default `display_name` renders "Launching Claude Code"
   - `show_launch_panel(display_name="Codex")` renders "Launching Codex"
   - `show_launch_context_panel()` title adapts similarly
   - Doctor summary with `provider_id="codex"` renders "Ready to run Codex"
6. Run ruff and mypy on all touched files.

## Must-Haves

- [ ] `show_launch_panel()` accepts `display_name` and renders it in the title
- [ ] `show_launch_context_panel()` accepts `display_name` and renders it in the title
- [ ] All 3 call sites pass the resolved provider's display name
- [ ] Doctor summary line is parameterized
- [ ] Tests pass

## Verification

- `uv run pytest tests/test_provider_branding.py -v` — all pass (including new tests)
- `uv run ruff check src/scc_cli/commands/launch/render.py src/scc_cli/commands/launch/flow.py src/scc_cli/commands/launch/flow_interactive.py src/scc_cli/commands/launch/sandbox.py src/scc_cli/doctor/render.py` — clean
- `uv run mypy src/scc_cli/commands/launch/render.py src/scc_cli/commands/launch/flow.py src/scc_cli/commands/launch/flow_interactive.py src/scc_cli/commands/launch/sandbox.py src/scc_cli/doctor/render.py` — clean

## Inputs

- ``src/scc_cli/commands/launch/render.py` — show_launch_panel() and show_launch_context_panel() with hardcoded titles`
- ``src/scc_cli/commands/launch/flow.py` — call site at line ~373, resolved_provider in scope at line ~256`
- ``src/scc_cli/commands/launch/flow_interactive.py` — call site at line ~713, start_request.provider_id accessible`
- ``src/scc_cli/commands/launch/sandbox.py` — call site at line ~142, start_request accessible`
- ``src/scc_cli/doctor/render.py` — render_doctor_results() with hardcoded 'Ready to run Claude Code'`
- ``src/scc_cli/core/provider_resolution.py` — get_provider_display_name() from T01`
- ``tests/test_provider_branding.py` — test file from T01 to extend`

## Expected Output

- ``src/scc_cli/commands/launch/render.py` — parameterized show_launch_panel() and show_launch_context_panel()`
- ``src/scc_cli/commands/launch/flow.py` — passes display_name to show_launch_panel()`
- ``src/scc_cli/commands/launch/flow_interactive.py` — passes display_name to show_launch_panel()`
- ``src/scc_cli/commands/launch/sandbox.py` — passes display_name to show_launch_panel()`
- ``src/scc_cli/doctor/render.py` — parameterized summary line`
- ``tests/test_provider_branding.py` — extended with launch panel and doctor tests`

## Verification

uv run pytest tests/test_provider_branding.py -v && uv run ruff check src/scc_cli/commands/launch/render.py src/scc_cli/commands/launch/flow.py src/scc_cli/commands/launch/flow_interactive.py src/scc_cli/commands/launch/sandbox.py src/scc_cli/doctor/render.py && uv run mypy src/scc_cli/commands/launch/render.py src/scc_cli/commands/launch/flow.py src/scc_cli/commands/launch/flow_interactive.py src/scc_cli/commands/launch/sandbox.py src/scc_cli/doctor/render.py
