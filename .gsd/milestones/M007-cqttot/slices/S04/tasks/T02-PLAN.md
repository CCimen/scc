---
estimated_steps: 25
estimated_files: 6
skills_used: []
---

# T02: Isolate Claude constants in OCI adapter, start_session.py, and document profile.py as Claude-only

## Description

The OCI sandbox adapter and start_session.py still import Claude-specific constants from core/constants.py (which T01 will have cleaned). This task localizes those imports and documents commands/profile.py as Claude-only.

After T01, core/constants.py no longer has AGENT_NAME, SANDBOX_IMAGE, SANDBOX_DATA_VOLUME etc. — so these imports will be broken and must be replaced.

## Steps

1. In `src/scc_cli/adapters/oci_sandbox_runtime.py`:
   - Remove `from scc_cli.core.constants import AGENT_NAME, SANDBOX_DATA_VOLUME` (line 18)
   - Add local constants: `_CLAUDE_AGENT_NAME = "claude"` and `_CLAUDE_DATA_VOLUME = "docker-claude-sandbox-data"`
   - At line 268, replace `SANDBOX_DATA_VOLUME` with `_CLAUDE_DATA_VOLUME` in the fallback
   - At line 339, replace `AGENT_NAME` with `_CLAUDE_AGENT_NAME`

2. In `src/scc_cli/application/start_session.py`:
   - Remove `from scc_cli.core.constants import SANDBOX_IMAGE` (line 21)
   - Add local constant: `_DOCKER_DESKTOP_CLAUDE_IMAGE = "docker/sandbox-templates:claude-code"`
   - At line 317 (approx), replace `SANDBOX_IMAGE` with `_DOCKER_DESKTOP_CLAUDE_IMAGE`

3. Update test files:
   - `tests/test_oci_sandbox_runtime.py`: Replace `from scc_cli.core.constants import AGENT_NAME, SANDBOX_DATA_VOLUME` with imports from the adapter's local constants, or inline the values
   - `tests/test_application_start_session.py`: Replace `from scc_cli.core.constants import AGENT_CONFIG_DIR, SANDBOX_IMAGE` — AGENT_CONFIG_DIR is `.claude`, inline it; SANDBOX_IMAGE replace with local value or import from start_session
   - `tests/test_start_session_image_routing.py`: Replace `from scc_cli.core.constants import SANDBOX_IMAGE` with inline value

4. In `src/scc_cli/commands/profile.py`:
   - Update the module-level docstring to clearly note this module is Claude-only: """Personal profile commands (Claude provider only). ... This module manages Claude-specific personal settings layered on top of team config. The hardcoded references to .claude/settings.local.json are intentional — this module operates exclusively within the Claude provider surface. Future provider generalization tracked separately."""

5. Verify: `uv run pytest tests/test_oci_sandbox_runtime.py tests/test_application_start_session.py tests/test_start_session_image_routing.py -v` all pass, `uv run ruff check` on touched files, `uv run mypy` on touched source files

## Must-Haves

- [ ] No OCI adapter or start_session.py imports from core.constants for Claude-specific values
- [ ] Test files updated to not import Claude constants from core.constants
- [ ] profile.py docstring documents Claude-only status
- [ ] All existing tests pass, ruff and mypy clean

## Inputs

- ``src/scc_cli/adapters/oci_sandbox_runtime.py` — imports AGENT_NAME, SANDBOX_DATA_VOLUME from core.constants`
- ``src/scc_cli/application/start_session.py` — imports SANDBOX_IMAGE from core.constants`
- ``src/scc_cli/commands/profile.py` — needs Claude-only documentation`
- ``tests/test_oci_sandbox_runtime.py` — imports AGENT_NAME, SANDBOX_DATA_VOLUME from core.constants`
- ``tests/test_application_start_session.py` — imports AGENT_CONFIG_DIR, SANDBOX_IMAGE from core.constants`
- ``tests/test_start_session_image_routing.py` — imports SANDBOX_IMAGE from core.constants`

## Expected Output

- ``src/scc_cli/adapters/oci_sandbox_runtime.py` — local _CLAUDE_AGENT_NAME, _CLAUDE_DATA_VOLUME constants`
- ``src/scc_cli/application/start_session.py` — local _DOCKER_DESKTOP_CLAUDE_IMAGE constant`
- ``src/scc_cli/commands/profile.py` — updated docstring noting Claude-only status`
- ``tests/test_oci_sandbox_runtime.py` — updated imports`
- ``tests/test_application_start_session.py` — updated imports`
- ``tests/test_start_session_image_routing.py` — updated imports`

## Verification

uv run pytest tests/test_oci_sandbox_runtime.py tests/test_application_start_session.py tests/test_start_session_image_routing.py -v && uv run ruff check src/scc_cli/adapters/oci_sandbox_runtime.py src/scc_cli/application/start_session.py src/scc_cli/commands/profile.py && uv run mypy src/scc_cli/adapters/oci_sandbox_runtime.py src/scc_cli/application/start_session.py src/scc_cli/commands/profile.py
