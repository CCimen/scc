---
estimated_steps: 50
estimated_files: 2
skills_used: []
---

# T02: Create shared launch preflight module with typed readiness model and pure/side-effect separation

Create src/scc_cli/commands/launch/preflight.py with clean three-function split and fully typed readiness model.

**Typed readiness model (not loose booleans/strings):**

```python
class ImageStatus(Enum):
    AVAILABLE = "available"
    MISSING = "missing"
    UNKNOWN = "unknown"

class AuthStatus(Enum):
    PRESENT = "present"
    MISSING = "missing"
    EXPIRED = "expired"
    UNKNOWN = "unknown"

class ProviderResolutionSource(Enum):
    EXPLICIT = "explicit"         # --provider flag
    RESUME = "resume"             # resumed session
    WORKSPACE_LAST_USED = "workspace_last_used"
    GLOBAL_PREFERRED = "global_preferred"
    AUTO_SINGLE = "auto_single"   # only one provider connected/allowed
    PROMPTED = "prompted"         # user chose from interactive picker

@dataclass(frozen=True)
class LaunchReadiness:
    provider_id: str
    resolution_source: ProviderResolutionSource
    image_status: ImageStatus
    auth_status: AuthStatus
    requires_image_bootstrap: bool   # derived: image_status is MISSING
    requires_auth_bootstrap: bool    # derived: auth_status is MISSING
    launch_ready: bool               # derived: both image + auth present
```

This prevents ad hoc branching glue — callers pattern-match on enum values, not string comparisons or bool combos.

**Pure decision functions (no I/O, fully testable):**
1. `allowed_provider_ids(normalized_org, team)` — moved from flow.py, made public
2. `resolve_launch_provider(...)` → `(provider_id, ProviderResolutionSource)` — wraps choose_start_provider() with standard parameter assembly. Returns resolved provider + source. Pure data in → data out.
3. `collect_launch_readiness(provider_id, resolution_source, adapters)` → `LaunchReadiness` — checks image availability and auth readiness via adapter, returns fully typed readiness state. No fixing, no side effects.

**Side-effect function:**
4. `ensure_launch_ready(readiness, *, console, non_interactive, show_notice)` — calls ensure_provider_image() and ensure_provider_auth() based on LaunchReadiness gaps. In non-interactive mode: raises typed ProviderNotReadyError with actionable guidance. Uses readiness.requires_image_bootstrap / requires_auth_bootstrap to decide — no re-probing.

**Architecture guards (D046):**
- Module stays command-layer only. No imports from core/ except types and errors.
- No provider-specific behavior — dispatches to provider_image.py and auth_bootstrap.py.
- No UI wording beyond structured error messages (user_message, suggested_action).
- Returns structured typed results; callers own rendering and launch orchestration.

**Caller pattern:**
```python
provider_id, source = resolve_launch_provider(...)
readiness = collect_launch_readiness(provider_id, source, adapters)
ensure_launch_ready(readiness, console=..., non_interactive=...)
deps, plan = prepare_live_start_plan(request, ...)
# caller owns: conflict resolution, output rendering, finalize_launch
```

Write unit tests for each function independently. Test the enum-based readiness model edge cases. Verify non-interactive contract: missing provider/image/auth → typed error with actionable guidance, never prompts.

## Inputs

- `src/scc_cli/commands/launch/provider_choice.py`
- `src/scc_cli/commands/launch/provider_image.py`
- `src/scc_cli/commands/launch/auth_bootstrap.py`
- `src/scc_cli/commands/launch/dependencies.py`

## Expected Output

- `src/scc_cli/commands/launch/preflight.py`
- `tests/test_launch_preflight.py`

## Verification

uv run pytest tests/test_launch_preflight.py -v && uv run ruff check src/scc_cli/commands/launch/preflight.py && uv run mypy src/scc_cli/commands/launch/preflight.py
