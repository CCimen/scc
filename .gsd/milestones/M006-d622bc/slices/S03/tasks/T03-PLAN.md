---
estimated_steps: 56
estimated_files: 21
skills_used: []
---

# T03: Sweep static help text, dashboard strings, docstrings, and add guardrail test

## Description

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

## Inputs

- ``tests/test_provider_branding.py` — test file from T01/T02 to extend with guardrail test`
- ``src/scc_cli/commands/launch/app.py` — help string at line 16`
- ``src/scc_cli/cli.py` — multiple help strings and docstrings`
- ``src/scc_cli/commands/worktree/container_commands.py` — help and message strings`
- ``src/scc_cli/commands/worktree/session_commands.py` — help and docstrings`
- ``src/scc_cli/commands/worktree/worktree_commands.py` — help and confirm prompt`
- ``src/scc_cli/commands/admin.py` — help and message strings`
- ``src/scc_cli/setup.py` — setup wizard strings`
- ``src/scc_cli/ui/git_interactive.py` — branch safety message`
- ``src/scc_cli/ui/dashboard/orchestrator_handlers.py` — dashboard item description`
- ``src/scc_cli/core/errors.py` — module docstring`
- ``src/scc_cli/core/constants.py` — module docstring`
- ``src/scc_cli/sessions.py` — module and function docstrings`
- ``src/scc_cli/commands/audit.py` — module docstring`
- ``src/scc_cli/doctor/__init__.py` — module docstring`

## Expected Output

- ``src/scc_cli/commands/launch/app.py` — provider-neutral help string`
- ``src/scc_cli/cli.py` — provider-neutral help and docstrings`
- ``src/scc_cli/commands/worktree/container_commands.py` — neutral strings`
- ``src/scc_cli/commands/worktree/session_commands.py` — neutral strings and docstrings`
- ``src/scc_cli/commands/worktree/worktree_commands.py` — neutral prompt and help`
- ``src/scc_cli/commands/admin.py` — neutral strings`
- ``src/scc_cli/setup.py` — neutral wizard strings`
- ``src/scc_cli/ui/git_interactive.py` — neutral branch message`
- ``src/scc_cli/ui/dashboard/orchestrator_handlers.py` — neutral dashboard description`
- ``src/scc_cli/core/errors.py` — updated docstring`
- ``src/scc_cli/core/constants.py` — updated docstring`
- ``src/scc_cli/sessions.py` — updated docstrings`
- ``src/scc_cli/commands/audit.py` — updated docstrings`
- ``src/scc_cli/doctor/__init__.py` — updated docstring`
- ``src/scc_cli/commands/launch/__init__.py` — updated docstring`
- ``src/scc_cli/commands/launch/flow.py` — updated docstring`
- ``src/scc_cli/commands/worktree/app.py` — updated docstring`
- ``src/scc_cli/commands/init.py` — updated comment`
- ``src/scc_cli/ui/dashboard/loaders.py` — updated docstring`
- ``src/scc_cli/application/dashboard_loaders.py` — updated docstring`
- ``tests/test_provider_branding.py` — extended with guardrail test scanning for 'Claude Code' in non-adapter code`

## Verification

uv run pytest tests/test_provider_branding.py -v && uv run pytest --rootdir "$PWD" -q && uv run ruff check
