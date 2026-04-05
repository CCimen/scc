# S04: Legacy Claude path isolation and Docker module cleanup

**Goal:** Claude-specific runtime constants removed from core/constants.py and localized in each consumer module. commands/profile.py documented as Claude-only. Guardrail test prevents re-introduction.
**Demo:** After this: docker/core.py, docker/credentials.py, docker/launch.py use local Claude constants instead of shared imports. commands/profile.py documented as Claude-only. No shared constant import from constants.py for Claude runtime values anywhere in the codebase.

## Tasks
- [x] **T01: Localize 9 Claude-specific constants from core/constants.py into 5 consumer modules (docker/, adapters/, application/)** — ## Description

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
  - Estimate: 30m
  - Files: src/scc_cli/docker/core.py, src/scc_cli/docker/credentials.py, src/scc_cli/docker/launch.py, src/scc_cli/core/constants.py, tests/test_docker_policy_integration.py
  - Verify: uv run pytest tests/test_docker.py tests/test_docker_core.py tests/test_docker_launch_characterization.py tests/test_docker_policy.py tests/test_docker_policy_integration.py tests/test_docker_org_config.py -v && uv run ruff check src/scc_cli/docker/ src/scc_cli/core/constants.py && uv run mypy src/scc_cli/docker/ src/scc_cli/core/constants.py
- [x] **T02: Renamed localized Claude constants to _CLAUDE_AGENT_NAME, _CLAUDE_DATA_VOLUME, _DOCKER_DESKTOP_CLAUDE_IMAGE and documented profile.py as Claude provider only** — ## Description

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
  - Estimate: 25m
  - Files: src/scc_cli/adapters/oci_sandbox_runtime.py, src/scc_cli/application/start_session.py, src/scc_cli/commands/profile.py, tests/test_oci_sandbox_runtime.py, tests/test_application_start_session.py, tests/test_start_session_image_routing.py
  - Verify: uv run pytest tests/test_oci_sandbox_runtime.py tests/test_application_start_session.py tests/test_start_session_image_routing.py -v && uv run ruff check src/scc_cli/adapters/oci_sandbox_runtime.py src/scc_cli/application/start_session.py src/scc_cli/commands/profile.py && uv run mypy src/scc_cli/adapters/oci_sandbox_runtime.py src/scc_cli/application/start_session.py src/scc_cli/commands/profile.py
- [x] **T03: Added guardrail test preventing Claude-specific constants in core/constants.py; fixed ruff I001 import-sorting violation in test_oci_sandbox_runtime.py** — ## Description

Add a guardrail test that prevents Claude-specific runtime constants from being re-added to core/constants.py. Verify the entire codebase has zero Claude-constant imports from core/constants.py. Run the full test suite.

The guardrail test follows the established pattern in tests/test_provider_branding.py (TestNoCloudeCodeInNonAdapterModules) — it scans source and fails on violations.

## Steps

1. Create `tests/test_no_claude_constants_in_core.py` with:
   - A test class `TestNoCloudeSpecificConstantsInCore` that reads `src/scc_cli/core/constants.py` and asserts none of the known Claude-specific constant names are defined there
   - Known Claude constant names to check: `AGENT_NAME`, `SANDBOX_IMAGE`, `AGENT_CONFIG_DIR`, `SANDBOX_DATA_VOLUME`, `SANDBOX_DATA_MOUNT`, `CREDENTIAL_PATHS`, `OAUTH_CREDENTIAL_KEY`, `DEFAULT_MARKETPLACE_REPO`
   - Use Python's `tokenize` module (per KNOWLEDGE.md guidance) to scan for NAME tokens matching these constants, avoiding false positives from comments or strings
   - A second test `test_no_claude_constant_imports_from_core` that scans all .py files under `src/scc_cli/` for `from.*core.constants import` lines containing any of the Claude-specific constant names
   - Both tests should produce actionable error messages listing the exact file and line

2. Verify the guardrail test passes: `uv run pytest tests/test_no_claude_constants_in_core.py -v`

3. Run rg scan to confirm zero Claude-constant imports from core.constants across the codebase: `rg 'from.*core\.constants import.*(AGENT_NAME|SANDBOX_IMAGE|SANDBOX_DATA_VOLUME|SANDBOX_DATA_MOUNT|OAUTH_CREDENTIAL_KEY|AGENT_CONFIG_DIR|CREDENTIAL_PATHS|DEFAULT_MARKETPLACE_REPO)' src/scc_cli/`

4. Run full suite: `uv run pytest -q` — must pass with zero regressions

5. Run `uv run ruff check` and `uv run mypy src/scc_cli/core/constants.py` for final lint/type check

## Must-Haves

- [ ] Guardrail test exists and passes
- [ ] Guardrail test would fail if a Claude constant were re-added to core/constants.py (verify by temporarily adding one)
- [ ] Full test suite passes with zero regressions
- [ ] Zero Claude-constant imports from core.constants in src/scc_cli/
  - Estimate: 20m
  - Files: tests/test_no_claude_constants_in_core.py
  - Verify: uv run pytest tests/test_no_claude_constants_in_core.py -v && uv run pytest -q && uv run ruff check tests/test_no_claude_constants_in_core.py
