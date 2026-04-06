---
estimated_steps: 8
estimated_files: 4
skills_used: []
---

# T01: Fix ensure_launch_ready to actually perform auth bootstrap

The current ensure_launch_ready() in preflight.py shows the auth bootstrap notice via show_notice() but never calls provider.bootstrap_auth(). This means dashboard and worktree paths that use ensure_launch_ready have a silent auth gap — the notice appears but the browser sign-in never triggers.

Steps:
1. Add an `adapters` parameter to ensure_launch_ready() so it can access the provider adapter.
2. In _ensure_auth(), after showing the notice in interactive mode, call the provider adapter's bootstrap_auth() method (same as auth_bootstrap.py does).
3. Wrap the bootstrap_auth() call with the same exception handling as auth_bootstrap.py: ProviderNotReadyError passes through, other exceptions get wrapped.
4. Update all existing callers (worktree_commands.py, orchestrator_handlers.py) to pass adapters.
5. Add a test proving bootstrap_auth() is called when auth is missing.
6. Update existing ensure_launch_ready tests for the new parameter.

## Inputs

- `src/scc_cli/commands/launch/auth_bootstrap.py — existing auth bootstrap logic to replicate`
- `src/scc_cli/commands/launch/preflight.py — current ensure_launch_ready without bootstrap_auth`

## Expected Output

- `Modified preflight.py with ensure_launch_ready calling bootstrap_auth()`
- `Updated callers passing adapters`
- `New test proving bootstrap_auth is called`

## Verification

uv run pytest tests/test_launch_preflight.py -v && uv run pytest tests/test_launch_preflight_guardrail.py -v && uv run ruff check
