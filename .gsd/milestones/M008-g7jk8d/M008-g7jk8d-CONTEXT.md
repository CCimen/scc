# M008 Context: Cross-Flow Consistency Hardening

## Origin
User directive after M007 completion. M007 touched auth, provider selection, setup, start/resume, dashboard orchestration, doctor output, image bootstrap, and container lifecycle. The risk is not one obvious bug but cross-flow inconsistency — different launch paths implementing the same concepts slightly differently.

## Branding: Sandboxed Coding CLI (D045)
D045 supersedes D030. The canonical product name is **Sandboxed Coding CLI**. All user-facing surfaces, package metadata, and branding already use this. M008 must not revert to "Sandboxed Code CLI". The .scc.yaml template in init.py already says "Sandboxed Coding CLI" — verify and guard with a test.

## Architecture Guard: Shared Preflight Module (D046)
The preflight module (`commands/launch/preflight.py`) must:
1. Stay command-layer only — not in core/ or application/
2. Not leak provider-specific behavior into core contracts
3. Not own UI wording beyond structured error messages
4. Separate pure decision logic from side effects:
   - `resolve_launch_provider()` — pure data in → data out
   - `collect_launch_readiness()` — pure, returns LaunchReadiness dataclass
   - `ensure_launch_ready()` — side effects: calls image/auth bootstrap
   - Callers own: conflict resolution, rendering, finalize_launch()

## Survey Findings (severity-ordered)

### Critical: Five-copy launch preflight duplication
The resolve-provider → ensure-image → ensure-auth → prepare-plan → conflict-resolution → launch sequence is **copied five times** with slight variations:

1. **flow.py start()** — full precedence with CLI flags, dry-run, personal profile
2. **flow_interactive.py run_start_wizard_flow()** — inline ~20 lines of provider resolution + full preflight, imports nothing from flow.py
3. **worktree_commands.py worktree_create_cmd()** — uses `resolve_active_provider()` directly, **missing** `ensure_provider_image()` and `ensure_provider_auth()` entirely
4. **orchestrator_handlers.py _handle_worktree_start()** — ~80 lines inline, imports private `_allowed_provider_ids` from flow.py
5. **orchestrator_handlers.py _handle_session_resume()** — ~80 lines inline, imports private `_allowed_provider_ids` from flow.py

### Critical: worktree create missing bootstrap
`worktree_create_cmd()` skips both image and auth bootstrap. If the image doesn't exist, `finalize_launch()` fails at the Docker layer with a raw error.

### Critical: _record_session_and_context doesn't thread provider_id to WorkContext

### Medium-High: Container lifecycle inventory
Need to verify scc list/stop/prune/status/resume all use the same SCC-managed inventory.

### Medium: Auth wording drift
"connected" vs "auth cache present" vs "sign-in required" — inconsistent across surfaces.

### Medium: No three-tier readiness distinction
"Ready" is overloaded. Setup and doctor don't distinguish auth cache present vs image present vs launch-ready.

### Medium: Hardcoded adapter dispatch maps in provider_choice.py and setup.py

### Medium-Low: Docker Desktop in active error messages

### Medium-Low: start_claude legacy variable name

### Edge cases to test:
- ask + workspace_last_used → prompt with preselection
- Resume after auth volume deleted
- Resume after image removed
- Explicit --provider with missing auth stays on that provider
- Auth bootstrap callback failure → clean SCC error
- Failed launch → don't write workspace preference
- Keep-existing conflict → consistent preference behavior across all sites
- Setup re-run with one provider connected → only ask missing questions
- Non-interactive with missing provider/image/auth → typed error, never prompt

## Key Code Locations
- `commands/launch/flow.py` — start(), _resolve_provider(), _allowed_provider_ids()
- `commands/launch/flow_interactive.py` — interactive_start(), run_start_wizard_flow()
- `commands/launch/flow_session.py` — _record_session_and_context()
- `commands/launch/provider_choice.py` — choose_start_provider(), collect_provider_readiness()
- `commands/launch/provider_image.py` — ensure_provider_image()
- `commands/launch/auth_bootstrap.py` — ensure_provider_auth()
- `commands/launch/dependencies.py` — _PROVIDER_DISPATCH, prepare_live_start_plan()
- `commands/worktree/worktree_commands.py` — worktree_create_cmd
- `commands/worktree/container_commands.py` — list_cmd, stop_cmd, prune_cmd
- `ui/dashboard/orchestrator_handlers.py` — _handle_worktree_start, _handle_session_resume
- `setup.py` — _run_provider_onboarding(), _render_provider_status()
- `commands/admin.py` — doctor_cmd
- `workspace_local_config.py` — workspace-local provider preference
- `application/provider_selection.py` — resolve_provider_preference()
- `core/provider_resolution.py` — resolve_active_provider()

## Constraints
- Small, typed, test-backed cleanups — no broad rewrites
- Characterization tests before any behavior change
- Every launch path must preserve its existing UX
- Legacy Docker Desktop code stays isolated and documented
- Product branding stays "Sandboxed Coding CLI" per D045
- Preflight module: command-layer only, no core leakage, pure/side-effect split (D046)
- M007 baseline: 4820 passed, 23 skipped, 2 xfailed
