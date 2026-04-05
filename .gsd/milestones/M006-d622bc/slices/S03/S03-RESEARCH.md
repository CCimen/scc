# S03 Research: Provider-aware branding, panels, diagnostics, and string cleanup

## Summary

This is targeted research. The work is a systematic string sweep: replacing hardcoded "Claude Code" / "Claude" references in user-facing strings with provider-aware alternatives that use `display_name` from `ProviderCapabilityProfile`. The pattern is well-established by S01 (provider resolution) and S02 (runner dispatch). No new technology, no ambiguous requirements. The main risk is completeness — missing one string means inconsistent UX.

## Requirement Coverage

- **R001 (maintainability):** The sweep directly reduces provider-coupling in user-facing code. Provider-aware helpers centralize branding so adding a third provider later doesn't require another string sweep.

## Recommendation

1. **Create a small `provider_display` helper** in `ui/branding.py` (or `core/provider_resolution.py`) that accepts a `provider_id` and returns the display name. This avoids threading `ProviderCapabilityProfile` objects through every UI function — a simple `get_provider_display_name("codex") → "Codex"` lookup is sufficient.
2. **Parameterize all user-facing functions** that currently hardcode "Claude Code" to accept a `display_name: str` parameter (with default `"Claude Code"` for backward compat).
3. **Leave Claude-specific adapter code alone** — `claude_agent_provider.py`, `claude_renderer.py`, `claude_settings.py`, `claude_safety_adapter.py`, `claude_agent_runner.py` are correctly Claude-specific.
4. **Leave marketplace/docker internals alone** — `.claude/` paths, `claude-plugins-official`, Docker Desktop sandbox labels are provider-infrastructure, not user-facing branding.
5. **Update docstrings/comments** that say "Claude Code" where the code is now provider-neutral, but don't over-rotate — module docstrings that describe Claude-specific adapters stay as-is.

## Implementation Landscape

### Bucket 1: User-facing runtime strings that MUST become provider-aware

These strings are displayed to the user and must reflect the active provider:

| File | Line(s) | Current string | Fix |
|------|---------|---------------|-----|
| `ui/branding.py` | 31, 37 | `"Sandboxed Claude CLI"` | Accept `display_name` param, e.g. `"Sandboxed {display_name} CLI"` or neutral `"SCC"`. **Design choice:** Since "SCC" is already the product brand, the header could become `"SCC  Sandboxed Code CLI"` (provider-neutral) or `"SCC  {provider} Edition"`. Simplest: make it `"SCC  Sandboxed Code CLI"` — SCC is the product, the provider is shown elsewhere. |
| `ui/branding.py` | 68 | `"Safe development environment manager for Claude Code"` | `"Safe development environment manager for {display_name}"` or neutral |
| `commands/launch/render.py` | 164, 309 | `"Launching Claude Code"` | `"Launching {display_name}"` — both `show_launch_panel()` and `show_launch_context_panel()` |
| `commands/launch/app.py` | 16 | `help="Start Claude Code in sandboxes."` | `help="Start agent in sandboxes."` (static help text, can't be dynamic) |
| `commands/launch/flow.py` | 120 | docstring `"Start Claude Code in a Docker sandbox."` | `"Start agent in a Docker sandbox."` |
| `doctor/render.py` | 115 | `"Ready to run Claude Code."` | `"Ready to run {display_name}."` — needs provider_id threaded to `render_doctor_results()` |
| `setup.py` | 127 | `"This does not affect Claude auth inside the container."` | `"This does not affect agent auth inside the container."` (setup runs before provider selection) |
| `setup.py` | 373 | `"Launch Claude in a workspace"` | `"Launch agent in a workspace"` (setup welcome, pre-provider) |
| `commands/worktree/container_commands.py` | 148 | `"Stop all running Claude Code sandboxes"` | `"Stop all running sandboxes"` (help text, static) |
| `commands/worktree/container_commands.py` | 174 | `"No Claude Code sandboxes are currently running."` | `"No sandboxes are currently running."` |
| `commands/worktree/session_commands.py` | 55 | `"List recent Claude Code sessions."` | `"List recent sessions."` (help text, static) |
| `commands/worktree/worktree_commands.py` | 136 | `"Start Claude after creating"` | `"Start agent after creating"` |
| `commands/worktree/worktree_commands.py` | 237 | `"Start Claude Code in this worktree?"` | `"Start {display_name} in this worktree?"` — needs provider_id |
| `commands/admin.py` | 462 | `"Restart Claude Code sandbox to see the changes."` | `"Restart sandbox to see the changes."` |
| `commands/admin.py` | 478 | `"Configure a custom status line for Claude Code."` | `"Configure a custom status line."` |
| `ui/git_interactive.py` | 89 | `"Claude Code work should happen on a feature branch."` | `"Agent work should happen on a feature branch."` |
| `ui/dashboard/orchestrator_handlers.py` | 739 | `description="Launch Claude"` | `description="Launch agent"` (or provider-aware if provider_id is accessible) |
| `ui/dashboard/loaders.py` | 40 | `"Load Sessions tab data showing recent Claude sessions."` | docstring only — update to `"recent sessions"` |
| `application/dashboard_loaders.py` | 274 | `"Load Sessions tab data showing recent Claude sessions."` | docstring only — same |
| `cli.py` | 61 | `"Safely run Claude Code with team configurations..."` | `"Safely run AI coding agents with team configurations..."` |
| `theme.py` | 342, 347 | `"SCC  Sandboxed Claude CLI"` | Same fix as `ui/branding.py` — these are ASCII art strings in theme |

### Bucket 2: Docstrings and comments — update for accuracy but low priority

| File | Description |
|------|-------------|
| `core/errors.py:2` | Module docstring says "Sandboxed Claude CLI" |
| `core/constants.py:5` | Module docstring says "Currently supports Claude Code" |
| `commands/launch/__init__.py:2` | "commands for starting Claude Code" |
| `commands/audit.py:3` | "Audit installed Claude Code plugins" |
| `commands/worktree/app.py:7` | "Claude Code session management" |
| `commands/worktree/session_commands.py:1` | Module docstring |
| `marketplace/sync.py:1` | Module docstring |
| `application/sync_marketplace.py:1` | Module docstring |
| `doctor/__init__.py:4` | Module docstring |
| `sessions.py:197,202` | Function docstrings for get_claude_sessions_dir/get_claude_recent_sessions |

### Bucket 3: Claude-specific adapter code — DO NOT CHANGE

These files correctly describe Claude-specific behavior:
- `adapters/claude_agent_provider.py` — Claude adapter
- `adapters/claude_agent_runner.py` — Claude adapter
- `adapters/claude_renderer.py` — Claude renderer
- `adapters/claude_settings.py` — Claude settings
- `adapters/claude_safety_adapter.py` — Claude safety adapter
- `marketplace/` (most files) — Claude marketplace infrastructure
- `docker/` (most files) — Docker internals referencing `.claude/` paths, container labels
- `commands/init.py:73` — SCC init config comment

### Bucket 4: Infrastructure constants — DO NOT CHANGE in this slice

These are runtime infrastructure, not user-facing branding:
- `core/constants.py`: `AGENT_NAME`, `SANDBOX_IMAGE`, `AGENT_CONFIG_DIR`, `SANDBOX_DATA_VOLUME`, `SANDBOX_DATA_MOUNT`, `OAUTH_CREDENTIAL_KEY`, `CREDENTIAL_PATHS` — all Claude-specific constants consumed by Docker/launch code. These become provider-specific via `ProviderRuntimeSpec` (D027), which is a separate concern from branding.
- `core/image_contracts.py`: `SCC_CLAUDE_IMAGE`, `SCC_CLAUDE_IMAGE_REF` — already correctly named as Claude-specific

## Key Design Decisions

### Provider display name helper

Rather than importing `ProviderCapabilityProfile` everywhere, create a lightweight lookup:

```python
# In core/provider_resolution.py (already exists, natural home)
_PROVIDER_DISPLAY_NAMES: dict[str, str] = {
    "claude": "Claude Code",
    "codex": "Codex",
}

def get_provider_display_name(provider_id: str) -> str:
    return _PROVIDER_DISPLAY_NAMES.get(provider_id, provider_id.title())
```

This keeps UI code from importing adapter modules. The display names match what `ProviderCapabilityProfile.display_name` returns for each provider.

### Static vs dynamic help text

Typer help strings are static — they're set at import time, not at runtime. For `--help` text, use provider-neutral language ("agent", "sandbox") rather than trying to make it dynamic. The provider name appears in runtime output (launch panel, doctor summary), not in `--help`.

### Branding header strategy

The version header (`ui/branding.py` and `theme.py`) currently says "Sandboxed Claude CLI". Options:
1. **Provider-neutral:** `"SCC  Sandboxed Code CLI"` — simplest, always correct
2. **Provider-parameterized:** `"SCC  Sandboxed {name} CLI"` — requires provider_id at version display time

Option 1 is cleaner. "SCC" is the product. The provider is shown in the launch panel and doctor output where it matters.

### Thread provider through call sites

For functions that need the display name at runtime (launch panel, doctor summary, worktree confirm), the `provider_id` (already resolved in `flow.py`) can be threaded as a string parameter. The display name lookup happens at the leaf.

## Natural Task Decomposition

The work splits into three independent streams:

**T01 — Provider display helper + branding core** (~30 min)
- Add `get_provider_display_name()` to `core/provider_resolution.py`
- Update `ui/branding.py`: parameterize `get_version_header()`, `get_brand_tagline()` to accept optional `provider_id` or go provider-neutral
- Update `theme.py` brand strings to match
- Tests for the helper + branding functions

**T02 — Launch panels and doctor string parameterization** (~30 min)
- `commands/launch/render.py`: Add `display_name` param to `show_launch_panel()` and `show_launch_context_panel()`
- Thread `provider_id` from `flow.py` → `show_launch_panel()` (3 call sites: `flow.py:373`, `flow_interactive.py:713`, `sandbox.py:142`)
- `doctor/render.py`: Parameterize `"Ready to run Claude Code"` 
- Tests for parameterized rendering

**T03 — Static help text, dashboard, setup, and docstring sweep** (~25 min)
- Update all Typer `help=` strings to provider-neutral language
- Update `setup.py`, `commands/admin.py`, `ui/git_interactive.py`, `commands/worktree/` strings
- Update `ui/dashboard/orchestrator_handlers.py` description
- Update module docstrings in Bucket 2
- Add guardrail test: scan user-facing string files for remaining "Claude Code" outside adapter modules

## Verification Strategy

- `uv run pytest --rootdir "$PWD" -q` — zero regressions
- `uv run ruff check` — clean
- `uv run mypy` on all touched files — clean
- New tests for `get_provider_display_name()`
- New tests for parameterized `show_launch_panel()` / `get_version_header()`
- Guardrail test scanning for hardcoded "Claude Code" in non-adapter user-facing modules

## Risks

- **Missed strings:** The grep audit above is thorough but some strings may be constructed dynamically. The guardrail test in T03 catches any that slip through.
- **Typer help text is static:** Can't be made dynamic. Using neutral language is the correct approach.
- **Box-drawing alignment:** The branding header uses fixed-width box-drawing. If the text changes length, the box must be re-measured. Minor but needs attention.
