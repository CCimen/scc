# S03: Provider-aware branding, panels, diagnostics, and string cleanup — UAT

**Milestone:** M006-d622bc
**Written:** 2026-04-05T00:33:12.615Z

## UAT: Provider-Aware Branding, Panels, Diagnostics, and String Cleanup

### Preconditions
- SCC installed and buildable (`uv sync`)
- Provider resolution from S01 functional (`scc provider show` works)

### Test Case 1: Provider Display Name Helper
**Steps:**
1. Run `uv run python -c "from scc_cli.core.provider_resolution import get_provider_display_name; print(get_provider_display_name('claude'))"`
2. Run same with `'codex'`
3. Run same with `'gemini'`

**Expected:**
1. Prints `Claude Code`
2. Prints `Codex`
3. Prints `Gemini` (title-cased fallback)

### Test Case 2: Branding Header Is Provider-Neutral
**Steps:**
1. Run `uv run python -c "from scc_cli.ui.branding import get_version_header; print(get_version_header())"`
2. Inspect output for product name

**Expected:**
- Contains "Sandboxed Code CLI"
- Does NOT contain "Sandboxed Claude"

### Test Case 3: CLI Help Text Is Provider-Neutral
**Steps:**
1. Run `uv run scc --help`
2. Run `uv run scc start --help`
3. Run `uv run scc sessions --help`
4. Run `uv run scc containers stop --help`

**Expected:**
- No output contains "Claude Code"
- Help text uses "agent", "AI coding agents", or "sandboxes" as appropriate

### Test Case 4: Launch Panel Adapts to Provider
**Steps:**
1. In Python: `from scc_cli.commands.launch.render import show_launch_panel`
2. Call with `display_name="Codex"` — inspect Rich Panel title
3. Call with default — inspect Rich Panel title

**Expected:**
- Codex call renders panel titled "Launching Codex"
- Default call renders panel titled "Launching Claude Code"

### Test Case 5: Doctor Summary Adapts to Provider
**Steps:**
1. In Python: `from scc_cli.doctor.render import render_doctor_results`
2. Call with a passing result and `provider_id="codex"`
3. Call with default

**Expected:**
- Codex call summary says "Ready to run Codex"
- Default call summary says "Ready to run Claude Code"

### Test Case 6: Guardrail Test Catches Regressions
**Steps:**
1. Run `uv run pytest tests/test_provider_branding.py::TestNoCloudeCodeInNonAdapterModules -v`
2. Temporarily add `# Claude Code test` to any non-adapter .py file
3. Run the test again
4. Revert the change

**Expected:**
- Step 1: Test passes
- Step 3: Test fails, reporting the file with the new reference
- Step 4: Test passes again

### Test Case 7: Theme ASCII Art Is Neutral
**Steps:**
1. Run `uv run python -c "from scc_cli.theme import HEADER_ART_UNICODE, HEADER_ART_ASCII; print(HEADER_ART_UNICODE); print(HEADER_ART_ASCII)"`

**Expected:**
- Both strings contain "Sandboxed Code CLI"
- Neither contains "Sandboxed Claude"

### Edge Case: Unknown Provider Display Name
**Steps:**
1. Run `uv run python -c "from scc_cli.core.provider_resolution import get_provider_display_name; print(get_provider_display_name('some-new-provider'))"`

**Expected:**
- Prints `Some-New-Provider` (title-cased, graceful fallback)
