---
id: T01
parent: S03
milestone: M006-d622bc
key_files:
  - src/scc_cli/core/provider_resolution.py
  - src/scc_cli/ui/branding.py
  - src/scc_cli/theme.py
  - tests/test_provider_branding.py
key_decisions:
  - get_brand_tagline() uses deferred import to avoid circular dependency between ui.branding and core.provider_resolution
duration: 
verification_result: passed
completed_at: 2026-04-05T00:08:13.391Z
blocker_discovered: false
---

# T01: Added get_provider_display_name() helper and replaced "Sandboxed Claude CLI" with "Sandboxed Code CLI" in branding header and theme ASCII art

**Added get_provider_display_name() helper and replaced "Sandboxed Claude CLI" with "Sandboxed Code CLI" in branding header and theme ASCII art**

## What Happened

Added get_provider_display_name() to core/provider_resolution.py with a _PROVIDER_DISPLAY_NAMES dict mapping claude→"Claude Code" and codex→"Codex", falling back to title-cased ID for unknown providers. Updated ui/branding.py version header to say "Sandboxed Code CLI" in both unicode and ASCII branches. Parameterized get_brand_tagline() with optional provider_id. Updated theme.py ASCII art to match. Wrote 10 tests covering display name lookups, version header neutrality, and tagline parameterization.

## Verification

uv run pytest tests/test_provider_branding.py -v — 10/10 passed. uv run ruff check on all three source files — clean. uv run mypy on all three source files — clean. Confirmed no "Sandboxed Claude" references remain in T01 target files.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_provider_branding.py -v` | 0 | ✅ pass | 8100ms |
| 2 | `uv run ruff check src/scc_cli/core/provider_resolution.py src/scc_cli/ui/branding.py src/scc_cli/theme.py` | 0 | ✅ pass | 8100ms |
| 3 | `uv run mypy src/scc_cli/core/provider_resolution.py src/scc_cli/ui/branding.py src/scc_cli/theme.py` | 0 | ✅ pass | 8100ms |

## Deviations

None.

## Known Issues

Remaining "Sandboxed Claude" references in errors.py, setup_ui.py, __init__.py, cli.py, setup.py, and commands/init.py are out of T01 scope — addressed by T02/T03.

## Files Created/Modified

- `src/scc_cli/core/provider_resolution.py`
- `src/scc_cli/ui/branding.py`
- `src/scc_cli/theme.py`
- `tests/test_provider_branding.py`
