---
estimated_steps: 9
estimated_files: 6
skills_used: []
---

# T02: Migrate flow.py and flow_interactive.py to shared preflight readiness path

Replace the inline ensure_provider_image + ensure_provider_auth calls in flow.py start() and flow_interactive.py run_start_wizard_flow() with collect_launch_readiness() + ensure_launch_ready() from preflight.py.

Key ordering constraint (D048): flow.py calls ensure_provider_image/auth AFTER prepare_live_start_plan and conflict_resolution. But the actual dependency is thin — ensure_provider_auth only uses plan.resume (to skip on resume) and dependencies.agent_provider (for auth_check/bootstrap_auth). For non-resume fresh starts, we can call collect_launch_readiness + ensure_launch_ready BEFORE plan construction, same as worktree/dashboard. For resume, the readiness check should skip auth bootstrap since auth is already present from the original session.

Steps:
1. In flow.py start(), move the readiness check to after provider resolution but before plan construction. Remove the ensure_provider_image and ensure_provider_auth calls after conflict resolution.
2. For the resume path: collect_launch_readiness still runs (to check image), but the resume flag means auth bootstrap is unnecessary — the session already authenticated. Add a `resume` parameter to ensure_launch_ready or handle this in the readiness model.
3. Same migration in flow_interactive.py run_start_wizard_flow().
4. Remove the ensure_provider_image and ensure_provider_auth imports from flow.py and flow_interactive.py.
5. Fix all affected tests.
6. Add flow.py and flow_interactive.py to the anti-drift guardrail if they aren't already there for the image/auth functions.

## Inputs

- `src/scc_cli/commands/launch/flow.py — current start() with inline image/auth`
- `src/scc_cli/commands/launch/flow_interactive.py — current run_start_wizard_flow with inline image/auth`

## Expected Output

- `flow.py using collect_launch_readiness + ensure_launch_ready, no ensure_provider_image/auth imports`
- `flow_interactive.py using same pattern`
- `Updated guardrail tests`

## Verification

uv run pytest tests/test_launch_preflight_guardrail.py tests/test_start_dryrun.py tests/test_integration.py -v && grep -rn ensure_provider_image src/scc_cli/commands/launch/flow.py && grep -rn ensure_provider_auth src/scc_cli/commands/launch/flow.py
