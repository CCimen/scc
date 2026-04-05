---
estimated_steps: 27
estimated_files: 4
skills_used: []
---

# T01: Add provider display helper and make branding provider-neutral

## Description

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

## Inputs

- ``src/scc_cli/core/provider_resolution.py` — existing module with resolve_active_provider(), KNOWN_PROVIDERS`
- ``src/scc_cli/ui/branding.py` — existing branding functions with hardcoded 'Claude' strings`
- ``src/scc_cli/theme.py` — ASCII art strings at lines 342/347 with 'Sandboxed Claude CLI'`

## Expected Output

- ``src/scc_cli/core/provider_resolution.py` — adds get_provider_display_name() and _PROVIDER_DISPLAY_NAMES dict`
- ``src/scc_cli/ui/branding.py` — provider-neutral header, parameterized tagline`
- ``src/scc_cli/theme.py` — updated ASCII art strings`
- ``tests/test_provider_branding.py` — new test file covering display helper and branding functions`

## Verification

uv run pytest tests/test_provider_branding.py -v && uv run ruff check src/scc_cli/core/provider_resolution.py src/scc_cli/ui/branding.py src/scc_cli/theme.py && uv run mypy src/scc_cli/core/provider_resolution.py src/scc_cli/ui/branding.py src/scc_cli/theme.py
