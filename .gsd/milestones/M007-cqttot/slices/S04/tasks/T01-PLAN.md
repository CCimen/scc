---
estimated_steps: 28
estimated_files: 5
skills_used: []
---

# T01: Localize Claude constants in docker/ modules and strip them from core/constants.py

## Description

The docker/ module (core.py, credentials.py, launch.py) is the Docker Desktop sandbox adapter — entirely Claude-specific. It currently imports Claude runtime constants from core/constants.py, creating a false impression these are shared. This task defines each constant locally in the consuming docker module and removes the Claude-specific constants from core/constants.py.

## Steps

1. In `src/scc_cli/docker/core.py`:
   - Remove `from ..core.constants import SANDBOX_IMAGE` (line 17)
   - Remove deferred `from ..core.constants import SANDBOX_DATA_MOUNT` (line 251)
   - Add module-level constants: `_SANDBOX_IMAGE = "docker/sandbox-templates:claude-code"` and `_SANDBOX_DATA_MOUNT = "/mnt/claude-data"`
   - Replace all usages of `SANDBOX_IMAGE` with `_SANDBOX_IMAGE` and `SANDBOX_DATA_MOUNT` with `_SANDBOX_DATA_MOUNT`

2. In `src/scc_cli/docker/credentials.py`:
   - Remove `from ..core.constants import OAUTH_CREDENTIAL_KEY, SANDBOX_DATA_VOLUME` (line 32)
   - Add module-level constants: `_OAUTH_CREDENTIAL_KEY = "claudeAiOauth"` and `_SANDBOX_DATA_VOLUME = "docker-claude-sandbox-data"`
   - Replace all usages

3. In `src/scc_cli/docker/launch.py`:
   - Remove `from ..core.constants import SAFETY_NET_POLICY_FILENAME, SANDBOX_DATA_MOUNT, SANDBOX_DATA_VOLUME` (line 16)
   - Add module-level constants: `_SAFETY_NET_POLICY_FILENAME = "effective_policy.json"`, `_SANDBOX_DATA_MOUNT = "/mnt/claude-data"`, `_SANDBOX_DATA_VOLUME = "docker-claude-sandbox-data"`
   - Replace all usages

4. In `src/scc_cli/core/constants.py`:
   - Remove these Claude-specific constants: `AGENT_NAME`, `SANDBOX_IMAGE`, `AGENT_CONFIG_DIR`, `SANDBOX_DATA_VOLUME`, `SANDBOX_DATA_MOUNT`, `SAFETY_NET_POLICY_FILENAME`, `CREDENTIAL_PATHS`, `OAUTH_CREDENTIAL_KEY`, `DEFAULT_MARKETPLACE_REPO`
   - Update the module docstring to reflect it now holds only product-level constants (CLI_VERSION, CURRENT_SCHEMA_VERSION, WORKTREE_BRANCH_PREFIX)
   - Keep the Usage example using the remaining constants

5. Update test files that imported docker-related constants from core/constants:
   - `tests/test_docker_policy_integration.py`: Replace `from scc_cli.core.constants import SAFETY_NET_POLICY_FILENAME` with `from scc_cli.docker.launch import _SAFETY_NET_POLICY_FILENAME as SAFETY_NET_POLICY_FILENAME` or inline the value

6. Verify: `uv run pytest tests/test_docker.py tests/test_docker_core.py tests/test_docker_launch_characterization.py tests/test_docker_policy.py tests/test_docker_policy_integration.py tests/test_docker_org_config.py -v` all pass, `uv run ruff check src/scc_cli/docker/ src/scc_cli/core/constants.py`, `uv run mypy src/scc_cli/docker/ src/scc_cli/core/constants.py`

## Must-Haves

- [ ] No docker/ module imports from core.constants for Claude-specific values
- [ ] core/constants.py retains only CLI_VERSION, CURRENT_SCHEMA_VERSION, WORKTREE_BRANCH_PREFIX and version helper
- [ ] All existing docker tests pass with zero regressions
- [ ] ruff check and mypy clean on touched files

## Inputs

- ``src/scc_cli/core/constants.py` — current source of Claude-specific constants to be removed`
- ``src/scc_cli/docker/core.py` — imports SANDBOX_IMAGE, SANDBOX_DATA_MOUNT from constants`
- ``src/scc_cli/docker/credentials.py` — imports OAUTH_CREDENTIAL_KEY, SANDBOX_DATA_VOLUME from constants`
- ``src/scc_cli/docker/launch.py` — imports SAFETY_NET_POLICY_FILENAME, SANDBOX_DATA_MOUNT, SANDBOX_DATA_VOLUME from constants`
- ``tests/test_docker_policy_integration.py` — imports SAFETY_NET_POLICY_FILENAME from core.constants`

## Expected Output

- ``src/scc_cli/core/constants.py` — stripped of all Claude-specific constants, docstring updated`
- ``src/scc_cli/docker/core.py` — local _SANDBOX_IMAGE, _SANDBOX_DATA_MOUNT constants`
- ``src/scc_cli/docker/credentials.py` — local _OAUTH_CREDENTIAL_KEY, _SANDBOX_DATA_VOLUME constants`
- ``src/scc_cli/docker/launch.py` — local _SAFETY_NET_POLICY_FILENAME, _SANDBOX_DATA_MOUNT, _SANDBOX_DATA_VOLUME constants`
- ``tests/test_docker_policy_integration.py` — updated import source`

## Verification

uv run pytest tests/test_docker.py tests/test_docker_core.py tests/test_docker_launch_characterization.py tests/test_docker_policy.py tests/test_docker_policy_integration.py tests/test_docker_org_config.py -v && uv run ruff check src/scc_cli/docker/ src/scc_cli/core/constants.py && uv run mypy src/scc_cli/docker/ src/scc_cli/core/constants.py
