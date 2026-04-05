# S03: Provider-aware branding, panels, diagnostics, and string cleanup

**Goal:** All user-facing strings (branding header, launch panel, doctor output, setup wizard, help text, dashboard) adapt to the active provider. No hardcoded "Claude Code" in runtime paths outside adapter modules. A guardrail test prevents regressions.
**Demo:** After this: All user-facing strings (branding header, launch panel, doctor output, setup wizard) adapt to the active provider. No hardcoded 'Claude Code' in runtime paths.

## Tasks
- [x] **T01: Added get_provider_display_name() helper and replaced "Sandboxed Claude CLI" with "Sandboxed Code CLI" in branding header and theme ASCII art** — ## Description

Create `get_provider_display_name()` in `core/provider_resolution.py` and update `ui/branding.py` + `theme.py` to use provider-neutral branding ("SCC — Sandboxed Code CLI" instead of "Sandboxed Claude CLI"). This is the foundation — T02 and T03 depend on the display name helper.

## Steps

1. Add `get_provider_display_name()` to `src/scc_cli/core/provider_resolution.py`:
   - `_PROVIDER_DISPLAY_NAMES: dict[str, str] = {"claude": "Claude Code", "codex": "Codex"}`
   - Function returns display name for known providers, `provider_id.title()` for unknown
2. Update `src/scc_cli/ui/branding.py`:
   - `get_version_header()`: Change "Sandboxed Claude CLI" → "Sandboxed Code CLI" in both unicode and ASCII branches. This is provider-neutral — SCC is the product, the provider is shown in launch panels.
   - `get_brand_tagline()`: Accept optional `provider_id: str | None = None` param. Default returns "Safe development environment manager" (neutral). When `provider_id` is passed, append the display name.
3. Update `src/scc_cli/theme.py`: Change the two ASCII art strings at lines 342/347 from "Sandboxed Claude CLI" → "Sandboxed Code CLI" to match branding.py.
4. Write tests in `tests/test_provider_branding.py`:
   - `get_provider_display_name("claude")` → "Claude Code"
   - `get_provider_display_name("codex")` → "Codex"
   - `get_provider_display_name("unknown")` → "Unknown"
   - `get_version_header()` contains "Sandboxed Code CLI" (not "Claude")
   - `get_brand_tagline()` default is provider-neutral
   - `get_brand_tagline(provider_id="codex")` includes "Codex"
5. Run `uv run ruff check` and `uv run mypy src/scc_cli/core/provider_resolution.py src/scc_cli/ui/branding.py src/scc_cli/theme.py` — both clean.

## Must-Haves

- [ ] `get_provider_display_name()` exists and returns correct names
- [ ] Branding header says "Sandboxed Code CLI" not "Sandboxed Claude CLI"
- [ ] `theme.py` ASCII art matches the updated branding
- [ ] Tests pass

## Verification

- `uv run pytest tests/test_provider_branding.py -v` — all pass
- `uv run ruff check src/scc_cli/core/provider_resolution.py src/scc_cli/ui/branding.py src/scc_cli/theme.py` — clean
- `uv run mypy src/scc_cli/core/provider_resolution.py src/scc_cli/ui/branding.py src/scc_cli/theme.py` — clean
  - Estimate: 25m
  - Files: src/scc_cli/core/provider_resolution.py, src/scc_cli/ui/branding.py, src/scc_cli/theme.py, tests/test_provider_branding.py
  - Verify: uv run pytest tests/test_provider_branding.py -v && uv run ruff check src/scc_cli/core/provider_resolution.py src/scc_cli/ui/branding.py src/scc_cli/theme.py && uv run mypy src/scc_cli/core/provider_resolution.py src/scc_cli/ui/branding.py src/scc_cli/theme.py
- [x] **T02: Added display_name parameter to show_launch_panel(), show_launch_context_panel(), and render_doctor_results(); threaded resolved provider at all call sites** — ## Description

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
  - Estimate: 30m
  - Files: src/scc_cli/commands/launch/render.py, src/scc_cli/commands/launch/flow.py, src/scc_cli/commands/launch/flow_interactive.py, src/scc_cli/commands/launch/sandbox.py, src/scc_cli/doctor/render.py, tests/test_provider_branding.py
  - Verify: uv run pytest tests/test_provider_branding.py -v && uv run ruff check src/scc_cli/commands/launch/render.py src/scc_cli/commands/launch/flow.py src/scc_cli/commands/launch/flow_interactive.py src/scc_cli/commands/launch/sandbox.py src/scc_cli/doctor/render.py && uv run mypy src/scc_cli/commands/launch/render.py src/scc_cli/commands/launch/flow.py src/scc_cli/commands/launch/flow_interactive.py src/scc_cli/commands/launch/sandbox.py src/scc_cli/doctor/render.py
- [ ] **T03: Sweep static help text, dashboard strings, docstrings, and add guardrail test** — ## Description

Update all remaining user-facing "Claude Code" references in non-adapter modules to provider-neutral language. Add a guardrail test that scans for regressions. This is the completeness gate — after T03, no user-facing code outside Claude-specific adapters should mention "Claude Code".

## Steps

1. Update static Typer `help=` strings (these are set at import time, can't be dynamic — use neutral language):
   - `src/scc_cli/commands/launch/app.py:16` — "Start Claude Code in sandboxes." → "Start agent in sandboxes."
   - `src/scc_cli/cli.py:61` — "Safely run Claude Code with team configurations..." → "Safely run AI coding agents with team configurations..."
   - `src/scc_cli/commands/worktree/container_commands.py:148` — "Stop all running Claude Code sandboxes" → "Stop all running sandboxes"
   - `src/scc_cli/commands/worktree/session_commands.py:55` — "List recent Claude Code sessions." → "List recent sessions."
   - `src/scc_cli/commands/worktree/worktree_commands.py:136` — "Start Claude after creating" → "Start agent after creating"
   - `src/scc_cli/commands/admin.py:478` — "Configure a custom status line for Claude Code." → "Configure a custom status line."
2. Update runtime prompt strings:
   - `src/scc_cli/commands/worktree/container_commands.py:174` — "No Claude Code sandboxes..." → "No sandboxes are currently running."
   - `src/scc_cli/commands/worktree/worktree_commands.py:237` — "Start Claude Code in this worktree?" → "Start agent in this worktree?"
   - `src/scc_cli/commands/admin.py:462` — "Restart Claude Code sandbox..." → "Restart sandbox to see the changes."
   - `src/scc_cli/ui/git_interactive.py:89` — "Claude Code work should happen on a feature branch" → "Agent work should happen on a feature branch"
   - `src/scc_cli/ui/dashboard/orchestrator_handlers.py:739` — `description="Launch Claude"` → `description="Launch agent"`
   - `src/scc_cli/setup.py:127` — "This does not affect Claude auth inside the container." → "This does not affect agent auth inside the container."
   - `src/scc_cli/setup.py:373` — "Launch Claude in a workspace" → "Launch agent in a workspace"
3. Update CLI help text and epilog in `src/scc_cli/cli.py`:
   - Line 5: "safely running Claude Code in Docker sandboxes" → "safely running AI coding agents in Docker sandboxes"
   - Lines 97-99: The rich-formatted help text — make provider-neutral
4. Update docstrings (Bucket 2 from research):
   - `src/scc_cli/core/errors.py:2` — "Sandboxed Claude CLI" → "Sandboxed Code CLI" (SCC)
   - `src/scc_cli/core/constants.py:5` — "Currently supports Claude Code" → "Supports multiple AI coding agents"
   - `src/scc_cli/commands/launch/__init__.py:2` — "commands for starting Claude Code" → "commands for starting agents"
   - `src/scc_cli/commands/launch/flow.py:120` — "Start Claude Code in a Docker sandbox." → "Start agent in a Docker sandbox."
   - `src/scc_cli/commands/audit.py:3,39,229` — update references
   - `src/scc_cli/commands/worktree/session_commands.py:1,182` — update module/function docstrings
   - `src/scc_cli/commands/worktree/app.py:7` — "Claude Code session management" → "session management"
   - `src/scc_cli/sessions.py:2,9,192,197,202` — update docstrings (keep function names unchanged since they're API)
   - `src/scc_cli/setup.py:2` — "Sandboxed Claude CLI" → "Sandboxed Code CLI"
   - `src/scc_cli/cli.py:3` — "Sandboxed Claude CLI" → "Sandboxed Code CLI"
   - `src/scc_cli/doctor/__init__.py:4` — update
   - `src/scc_cli/ui/dashboard/loaders.py:40` — "recent Claude sessions" → "recent sessions"
   - `src/scc_cli/application/dashboard_loaders.py:274` — same
   - `src/scc_cli/ui/dashboard/orchestrator_handlers.py:282,425` — update docstrings
   - `src/scc_cli/ui/git_interactive.py:64` — update docstring
   - `src/scc_cli/commands/admin.py:360` — "Configure Claude Code status line" → "Configure status line"
   - `src/scc_cli/commands/init.py:73` — "SCC (Sandboxed Claude CLI)" → "SCC (Sandboxed Code CLI)"
5. Add guardrail test in `tests/test_provider_branding.py`:
   - Scan all `.py` files under `src/scc_cli/` for "Claude Code" or "Sandboxed Claude"
   - Exclude files in `adapters/claude_*`, `marketplace/` (infrastructure), and test files
   - Allow matches in string literals that are clearly Claude-adapter-specific (e.g. `CLAUDE.md` references)
   - Test fails if any unexpected matches remain
6. Run full suite: `uv run pytest --rootdir "$PWD" -q` — zero regressions. Run ruff check. Run mypy on all touched files.

## Must-Haves

- [ ] All Typer help strings use provider-neutral language
- [ ] All runtime prompts/messages use provider-neutral language
- [ ] Module docstrings updated where they reference "Claude Code" outside adapter modules
- [ ] Guardrail test exists and passes — no "Claude Code" in non-adapter user-facing code
- [ ] Full test suite has zero regressions

## Verification

- `uv run pytest tests/test_provider_branding.py -v` — all pass (including guardrail)
- `uv run pytest --rootdir "$PWD" -q` — zero regressions
- `uv run ruff check` — clean
- `grep -rn 'Claude Code' src/scc_cli/ --include='*.py' | grep -v claude_ | grep -v marketplace/ | grep -v __pycache__` — only allowed adapter references remain
  - Estimate: 35m
  - Files: src/scc_cli/commands/launch/app.py, src/scc_cli/commands/launch/flow.py, src/scc_cli/commands/launch/__init__.py, src/scc_cli/commands/worktree/container_commands.py, src/scc_cli/commands/worktree/session_commands.py, src/scc_cli/commands/worktree/worktree_commands.py, src/scc_cli/commands/worktree/app.py, src/scc_cli/commands/admin.py, src/scc_cli/commands/audit.py, src/scc_cli/commands/init.py, src/scc_cli/cli.py, src/scc_cli/setup.py, src/scc_cli/core/errors.py, src/scc_cli/core/constants.py, src/scc_cli/sessions.py, src/scc_cli/ui/git_interactive.py, src/scc_cli/ui/dashboard/orchestrator_handlers.py, src/scc_cli/ui/dashboard/loaders.py, src/scc_cli/application/dashboard_loaders.py, src/scc_cli/doctor/__init__.py, tests/test_provider_branding.py
  - Verify: uv run pytest tests/test_provider_branding.py -v && uv run pytest --rootdir "$PWD" -q && uv run ruff check
