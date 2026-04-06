---
estimated_steps: 6
estimated_files: 3
skills_used: []
---

# T03: Refactor flow.py start() and flow_interactive.py run_start_wizard_flow() to use shared preflight

Refactor the two CLI launch paths:

1. flow.py start(): Replace the inline _resolve_provider() + ensure_provider_image() + ensure_provider_auth() + prepare_live_start_plan() sequence with calls to resolve_launch_provider(), collect_launch_readiness(), ensure_launch_ready(). Keep prepare_live_start_plan(), conflict resolution, dry-run, personal profile, and output rendering as flow.py-specific caller-owned concerns.
2. flow_interactive.py run_start_wizard_flow(): Replace the inline allowed_provider_ids + choose_start_provider + ensure_provider_image + ensure_provider_auth + prepare_live_start_plan sequence with the same three-function calls.
3. Remove _resolve_provider() from flow.py (now resolve_launch_provider in preflight.py). Remove _allowed_provider_ids() from flow.py (now allowed_provider_ids in preflight.py).
4. Update imports in both files. Ensure re-exports in __init__.py stay clean.

Verify characterization tests still pass. Verify non-interactive contract holds.

## Inputs

- `src/scc_cli/commands/launch/preflight.py`

## Expected Output

- `src/scc_cli/commands/launch/flow.py`
- `src/scc_cli/commands/launch/flow_interactive.py`

## Verification

uv run pytest tests/test_launch_preflight_characterization.py tests/test_launch_preflight.py -v && uv run ruff check src/scc_cli/commands/launch/flow.py src/scc_cli/commands/launch/flow_interactive.py && uv run mypy src/scc_cli/commands/launch/flow.py src/scc_cli/commands/launch/flow_interactive.py
