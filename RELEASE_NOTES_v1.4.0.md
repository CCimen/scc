# SCC CLI v1.4.0 Release Notes

**Release Date**: December 30, 2025

## Overview

v1.4.0 delivers a comprehensive TUI architecture overhaul, enhanced CLI UX/DX, safety-net policy injection for container security, and schema unification with a Validation Gate pattern. This release includes 67 files changed with 5,547 insertions and 2,276 deletions.

---

## Highlights

| Category | Changes |
|----------|---------|
| TUI Architecture | Centralized design system, dashboard refactoring, terminal capability detection |
| CLI UX/DX | Quick Resume improvements, workspace-to-team pinning, worktree safety |
| Security | Safety-net policy injection with cross-platform reliability |
| Schema | Validation Gate pattern for configuration conformance |
| Testing | 3,049 tests passing (~78% coverage) |

---

## TUI Output Architecture

### Centralized Design System

A new theme system provides consistent styling across all CLI output:

**New Files:**
- `src/scc_cli/theme.py` - Design tokens (Colors, Borders, Indicators, Spinners)
- `src/scc_cli/ui/branding.py` - ASCII art header with unicode/ASCII fallback

**Key Features:**
- `Colors` class: Brand colors (BRAND, SUCCESS, WARNING, ERROR, INFO)
- `Borders` class: Panel border styles and footer separators
- `Indicators` class: Status symbols with `unicode` parameter for graceful degradation
- `Spinners` class: Contextual spinner types (DEFAULT, NETWORK, DOCKER, SETUP)

```python
# Example: Graceful unicode fallback
Indicators.get("PASS", unicode=True)   # Returns "✓"
Indicators.get("PASS", unicode=False)  # Returns "OK"
```

### Dashboard Refactoring

The monolithic 1,457-line `dashboard.py` has been split into a modular package:

```
src/scc_cli/ui/dashboard/
├── __init__.py      # Public API (backward compatible imports)
├── _dashboard.py    # Core Dashboard class (669 lines)
├── models.py        # Data structures (DashboardState, TabData) (184 lines)
├── loaders.py       # Tab data loading functions (369 lines)
└── orchestrator.py  # Event loop and action dispatch (337 lines)
```

**Benefits:**
- Strict dependency direction: orchestrator → loaders → models
- Lazy imports maintain backward compatibility
- Clear separation of concerns

### Terminal Capability Detection

New `TerminalCaps` dataclass in `console.py` centralizes all terminal capability checks:

```python
@dataclass(frozen=True)
class TerminalCaps:
    can_render: bool    # stderr TTY + not JSON mode
    can_animate: bool   # can_render + TERM != dumb
    can_prompt: bool    # stdin TTY + not JSON + not CI
    colors: bool        # NO_COLOR/FORCE_COLOR + TTY check
    unicode: bool       # encoding + platform heuristics
```

**Stream Contract Enforcement:**
- stdout: JSON only (or nothing in human mode)
- stderr: All Rich UI output (panels, spinners, prompts)

### JSON Output Mode Hardening

- Flag conflict detection (`--json` + `--interactive` fast-fail)
- Subprocess-level stream contract tests
- All human UI routed through `get_err_console()` factory

---

## CLI UX/DX Improvements

### Quick Resume Enhancement

Sessions tab now uses a two-step interaction pattern:

1. **First Enter**: Opens details pane (shows session info)
2. **Second Enter**: Resumes the session

Footer hints update contextually:
- Details closed: `Enter details`
- Details open: `Enter resume`

### Multi-Project Support

New workspace-to-team pinning enables automatic team switching:

```bash
# Pin current workspace to a team
scc team pin <team-name>

# Automatic team switching when entering pinned workspace
cd ~/work/project-a  # Switches to team-a automatically
```

### Worktree Safety

Enhanced worktree commands with better error handling:
- Clear error messages for non-git directories
- Graceful handling of missing worktrees
- Improved cleanup on failed operations

### Contextual Help Hints

New help hints appear in empty states and error conditions:

| State | Hint |
|-------|------|
| No containers | "No containers found. Run `scc start <path>` to create one." |
| No sessions | "No sessions found. Start a container to create sessions." |
| Docker not running | "Docker is not running. Start Docker Desktop to continue." |

---

## Safety-Net Policy Injection

### Overview

Safety-net policies provide automated security guardrails for AI-assisted development:

```json
{
  "safety_net": {
    "enabled": true,
    "policy_path": "https://example.com/policies/security.md",
    "injection_point": "system_prompt"
  }
}
```

### Cross-Platform Reliability

- **Windows**: Proper path handling for WSL2 and native Windows
- **macOS**: Symlink handling for credential persistence
- **Linux**: Standard XDG path compliance

### Policy Validation

Policies are validated before injection:
- Schema conformance checking
- URL accessibility verification
- Content sanitization

---

## Schema Unification

### Validation Gate Pattern

All configuration loading now passes through a validation gate:

```python
def load_with_validation(path: Path, schema: str) -> dict:
    """Load and validate configuration against schema."""
    data = json.loads(path.read_text())
    validate_against_schema(data, schema)
    return data
```

### Schema Registry

Bundled JSON schemas for offline validation:
- `org_config.schema.json` - Organization configuration
- `team_profile.schema.json` - Team profile settings
- `user_config.schema.json` - User preferences

---

## Bug Fixes

### Case-Insensitive Pattern Matching

Fixed inconsistent case handling in:
- Plugin name matching
- Team name lookups
- Profile resolution

### Cross-Platform Reliability

- **Windows crash fix**: Safe `termios` import handling
- **WSL2 path detection**: Improved Windows mount path detection
- **Unicode detection**: Platform-specific encoding checks

### Start Command Robustness

- Added `--standalone`, `--offline`, and `--dry-run` flags
- Better error handling for missing Docker
- Improved workspace validation

---

## Documentation Updates

### New Documentation

| File | Description |
|------|-------------|
| `docs/SAFETY_NET.md` | Safety-net policy documentation |
| `README.md` | Complete rewrite for clarity |

### Updated Command Table

| Flag | Description |
|------|-------------|
| `--standalone` | Run without organization configuration |
| `--offline` | Skip remote configuration fetch |
| `--dry-run` | Preview configuration without launching |

---

## Testing

### Test Coverage

| Metric | Value |
|--------|-------|
| Total Tests | 3,049 |
| Coverage | ~78% |
| Test Files | 57 |

### New Test Suites

| File | Purpose |
|------|---------|
| `test_json_output.py` | JSON output purity validation |
| `test_stream_contract.py` | Subprocess-level stream verification |
| `test_ui_snapshots.py` | UI structural regression tests |
| `test_ui_gate.py` | Flag conflict detection |
| `test_safety_policy.py` | Policy injection validation |
| `test_marketplace_federation.py` | Marketplace federation integration tests |

---

## Breaking Changes

None. All changes are backward compatible.

---

## Upgrade Guide

```bash
# Upgrade from v1.3.0
pip install --upgrade scc-cli

# Or with pipx
pipx upgrade scc-cli

# Verify installation
scc --version  # Should show 1.4.0
scc doctor     # Run health checks
```

---

## File Changes Summary

| Category | Files | Insertions | Deletions |
|----------|-------|------------|-----------|
| TUI Architecture | 15 | 2,100 | 1,500 |
| CLI Commands | 8 | 450 | 200 |
| Safety-Net | 5 | 600 | 50 |
| Schema | 4 | 300 | 100 |
| Tests | 13 | 1,500 | 300 |
| Documentation | 5 | 400 | 100 |
| **Total** | **67** | **5,547** | **2,276** |

---

## Contributors

- SCC CLI Development Team

---

## What's Changed

* fix: enforce case-insensitive pattern matching for security by @CCimen in https://github.com/CCimen/scc/pull/27
* feat(tests): add integration tests for marketplace federation by @CCimen in https://github.com/CCimen/scc/pull/28
* docs: add scc-safety-net plugin documentation and example config by @CCimen in https://github.com/CCimen/scc/pull/29
* fix: harden policy injection for cross-platform reliability by @CCimen in https://github.com/CCimen/scc/pull/30
* Feature/schema unification by @CCimen in https://github.com/CCimen/scc/pull/31
* test: add comprehensive safety-net policy injection tests by @CCimen in https://github.com/CCimen/scc/pull/32
* chore: bump version to 1.4.0 by @CCimen in https://github.com/CCimen/scc/pull/33
* Feature/start command robustness by @CCimen in https://github.com/CCimen/scc/pull/34
* feat: implement UX/DX improvements (Phase 0-4) by @CCimen in https://github.com/CCimen/scc/pull/35
* TUI Output Architecture Improvements by @CCimen in https://github.com/CCimen/scc/pull/36

**Full Changelog**: https://github.com/CCimen/scc/compare/v1.3.0...v1.4.0

---

## Links

- [GitHub Repository](https://github.com/CCimen/scc)
- [Documentation](https://github.com/CCimen/scc/tree/main/docs)
- [Issue Tracker](https://github.com/CCimen/scc/issues)
