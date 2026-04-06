# S01: Provider resolution consistency across worktree create and wizard flow

**Goal:** Collapse five copies of resolve-provider/ensure-image/ensure-auth/launch into one shared preflight module with clean separation of pure decision logic from side effects. All launch paths produce identical behavior for the same inputs.
**Demo:** After this: worktree create --start uses choose_start_provider() with full precedence. run_start_wizard_flow() reuses shared resolution. WorkContext records provider_id. start_claude renamed.

## Tasks
- [x] **T01: 43 characterization tests capture provider resolution behavior across all five launch preflight sites and the WorkContext provider_id gap** — Write characterization tests capturing the current behavior of each launch preflight copy:

1. flow.py start() — provider resolution with full precedence (cli_flag, resume, workspace_last_used, config, auth probing)
2. flow_interactive.py run_start_wizard_flow() — inline provider resolution (no cli_flag, no resume_provider)
3. worktree_commands.py worktree_create_cmd() — uses resolve_active_provider() directly (missing workspace_last_used, missing image/auth bootstrap)
4. orchestrator_handlers.py _handle_worktree_start() — inline resolution + image + auth (imports _allowed_provider_ids from flow.py)
5. orchestrator_handlers.py _handle_session_resume() — inline resolution with resume_provider + image + auth

Also characterize:
- _record_session_and_context: verify WorkContext.provider_id is currently None
- Non-interactive behavior: verify each site's behavior when non_interactive=True and provider/image/auth is missing

These tests document current behavior as the regression baseline.
  - Estimate: 40min
  - Files: tests/test_launch_preflight_characterization.py
  - Verify: uv run pytest tests/test_launch_preflight_characterization.py -v
- [x] **T02: Created commands/launch/preflight.py with typed LaunchReadiness model and three-function preflight split (resolve → collect → ensure), verified by 39 new tests** — Create src/scc_cli/commands/launch/preflight.py with clean three-function split and fully typed readiness model.

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
  - Estimate: 50min
  - Files: src/scc_cli/commands/launch/preflight.py, tests/test_launch_preflight.py
  - Verify: uv run pytest tests/test_launch_preflight.py -v && uv run ruff check src/scc_cli/commands/launch/preflight.py && uv run mypy src/scc_cli/commands/launch/preflight.py
- [x] **T03: Replaced inline _resolve_provider() and _allowed_provider_ids() in flow.py and flow_interactive.py with shared preflight.resolve_launch_provider(), eliminating provider resolution duplication across both launch paths** — Refactor the two CLI launch paths:

1. flow.py start(): Replace the inline _resolve_provider() + ensure_provider_image() + ensure_provider_auth() + prepare_live_start_plan() sequence with calls to resolve_launch_provider(), collect_launch_readiness(), ensure_launch_ready(). Keep prepare_live_start_plan(), conflict resolution, dry-run, personal profile, and output rendering as flow.py-specific caller-owned concerns.
2. flow_interactive.py run_start_wizard_flow(): Replace the inline allowed_provider_ids + choose_start_provider + ensure_provider_image + ensure_provider_auth + prepare_live_start_plan sequence with the same three-function calls.
3. Remove _resolve_provider() from flow.py (now resolve_launch_provider in preflight.py). Remove _allowed_provider_ids() from flow.py (now allowed_provider_ids in preflight.py).
4. Update imports in both files. Ensure re-exports in __init__.py stay clean.

Verify characterization tests still pass. Verify non-interactive contract holds.
  - Estimate: 35min
  - Files: src/scc_cli/commands/launch/flow.py, src/scc_cli/commands/launch/flow_interactive.py, tests/test_launch_preflight_characterization.py
  - Verify: uv run pytest tests/test_launch_preflight_characterization.py tests/test_launch_preflight.py -v && uv run ruff check src/scc_cli/commands/launch/flow.py src/scc_cli/commands/launch/flow_interactive.py && uv run mypy src/scc_cli/commands/launch/flow.py src/scc_cli/commands/launch/flow_interactive.py
- [x] **T04: Fixed 26 pre-existing test failures across guardrail, mock compatibility, and provider resolution tests** — Refactor the three remaining launch paths:

1. orchestrator_handlers.py _handle_worktree_start(): Replace ~80 lines of inline preflight with resolve_launch_provider() + collect_launch_readiness() + ensure_launch_ready(). Remove import of flow.py::_allowed_provider_ids.
2. orchestrator_handlers.py _handle_session_resume(): Same — replace inline preflight. Pass session.provider_id as resume_provider.
3. worktree_commands.py worktree_create_cmd(): Replace resolve_active_provider() with resolve_launch_provider() + collect_launch_readiness() + ensure_launch_ready(). This adds image and auth bootstrap that were completely missing.
4. Rename start_claude parameter to start_agent (keep --start/--no-start CLI flags).
5. Thread provider_id through _record_session_and_context() → WorkContext constructor.

Verify characterization tests still pass. The worktree create tests should now show enhanced behavior (image + auth bootstrap).
  - Estimate: 45min
  - Files: src/scc_cli/ui/dashboard/orchestrator_handlers.py, src/scc_cli/commands/worktree/worktree_commands.py, src/scc_cli/commands/launch/flow_session.py, tests/test_launch_preflight_characterization.py
  - Verify: uv run pytest tests/test_launch_preflight_characterization.py tests/test_launch_preflight.py -v && uv run ruff check src/scc_cli/ui/dashboard/orchestrator_handlers.py src/scc_cli/commands/worktree/worktree_commands.py src/scc_cli/commands/launch/flow_session.py && uv run mypy src/scc_cli/ui/dashboard/orchestrator_handlers.py src/scc_cli/commands/worktree/worktree_commands.py src/scc_cli/commands/launch/flow_session.py
- [x] **T05: Created structural guardrail tests preventing inline provider resolution drift and verifying single-source provider metadata** — **Structural anti-drift guardrail (main maintainability guard of M008):**

Create tests/test_launch_preflight_guardrail.py with a structural test that scans the five launch entry-point files for inline preflight orchestration. The test should:
1. Parse each of the five files (flow.py, flow_interactive.py, worktree_commands.py, orchestrator_handlers.py ×2 functions) using tokenize or AST
2. Assert that none of them contain direct calls to `ensure_provider_image()`, `ensure_provider_auth()`, `choose_start_provider()`, or `resolve_active_provider()` — all of which should now flow through preflight.py
3. Assert that each file imports from `commands.launch.preflight`
4. This is a mechanical guardrail — if someone adds inline preflight back to one of the five sites, this test fails immediately.

Pattern: similar to test_no_claude_constants_in_core.py and test_import_boundaries.py — structural scanning, not behavioral mocking.

**Single provider metadata source verification:**
5. Add a guardrail test (in the same file or test_docs_truthfulness.py) verifying that image refs, display names, and adapter lookup all resolve from one source — the ProviderRuntimeSpec registry (core/provider_registry.py) and _PROVIDER_DISPATCH (dependencies.py). The test scans for hardcoded image refs or display name strings outside of those two canonical locations plus the adapter modules that own them.
6. This catches the exact consistency bug M008 is cleaning: scattered provider constants that drift.

**Full verification gate:**
7. ruff check on all touched files
8. mypy on all touched source files
9. Focused pytest on characterization, preflight, and guardrail tests
10. Full pytest suite (must be >= 4820 with zero regressions)
11. Verify via rg that start_claude no longer appears in the codebase
12. Verify preflight.py has no imports from core/ except types/errors (D046 architecture guard)
  - Estimate: 25min
  - Files: tests/test_launch_preflight_guardrail.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest -q
