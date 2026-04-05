# S04 Research: Legacy Claude Path Isolation and Docker Module Cleanup

## Summary

This is a targeted cleanup slice. The `docker/` module (Docker Desktop sandbox — Claude-only) and two other consumers import Claude-specific runtime constants (`SANDBOX_IMAGE`, `SANDBOX_DATA_VOLUME`, `SANDBOX_DATA_MOUNT`, `OAUTH_CREDENTIAL_KEY`, `AGENT_NAME`, `SAFETY_NET_POLICY_FILENAME`) from `core/constants.py`. This creates a false impression that these values are shared/provider-neutral when they are Claude-specific. The fix: move Claude runtime values into local constants in each consumer module, document `commands/profile.py` as Claude-only, and add a guardrail test that prevents future Claude-constant imports from `core/constants.py`.

## Recommendation

Inline Claude-specific constants as module-level locals in each consumer. Remove the Claude-specific constants from `core/constants.py` (keep only genuinely shared: `CLI_VERSION`, `CURRENT_SCHEMA_VERSION`, `WORKTREE_BRANCH_PREFIX`). Add a guardrail test. This is mechanical refactoring with no behavioral change.

## Implementation Landscape

### Files that import Claude-specific constants from `core/constants.py`

| File | Constants imported | Action |
|---|---|---|
| `docker/core.py` | `SANDBOX_IMAGE`, `SANDBOX_DATA_MOUNT` (deferred import at L251) | Define as local constants |
| `docker/credentials.py` | `OAUTH_CREDENTIAL_KEY`, `SANDBOX_DATA_VOLUME` | Define as local constants |
| `docker/launch.py` | `SAFETY_NET_POLICY_FILENAME`, `SANDBOX_DATA_MOUNT`, `SANDBOX_DATA_VOLUME` | Define as local constants |
| `adapters/oci_sandbox_runtime.py` | `AGENT_NAME`, `SANDBOX_DATA_VOLUME` | Replace `SANDBOX_DATA_VOLUME` with fallback from registry; replace `AGENT_NAME` with local constant or provider-derived value |
| `application/start_session.py` | `SANDBOX_IMAGE` | Replace with local constant for Docker Desktop fallback path |

### Test files that import Claude-specific constants

| File | Constants imported | Action |
|---|---|---|
| `tests/test_oci_sandbox_runtime.py` | `AGENT_NAME`, `SANDBOX_DATA_VOLUME` | Import from the module where the constant now lives, or inline |
| `tests/test_application_start_session.py` | `AGENT_CONFIG_DIR`, `SANDBOX_IMAGE` | Import from new location or inline |
| `tests/test_start_session_image_routing.py` | `SANDBOX_IMAGE` | Import from new location or inline |
| `tests/test_docker_policy_integration.py` | `SAFETY_NET_POLICY_FILENAME` | Import from `docker.launch` or inline |

### `commands/profile.py` — Claude-only documentation

This module has hardcoded `.claude/settings.local.json` references in user-facing strings (lines 246, 270, 318, 440, 486, 508). It does NOT import from `core/constants.py`. The roadmap wants it documented as Claude-only. Action: add a module-level docstring note and a comment block marking it as Claude-specific, pending future provider generalization.

### Constants to remove from `core/constants.py`

These are Claude-specific and should be removed after consumers are migrated:

- `AGENT_NAME = "claude"` — Claude binary name
- `SANDBOX_IMAGE = "docker/sandbox-templates:claude-code"` — Claude Docker Desktop template
- `AGENT_CONFIG_DIR = ".claude"` — Claude config directory
- `SANDBOX_DATA_VOLUME = "docker-claude-sandbox-data"` — Claude volume name
- `SANDBOX_DATA_MOUNT = "/mnt/claude-data"` — Claude mount path
- `CREDENTIAL_PATHS` — Claude credential file paths
- `OAUTH_CREDENTIAL_KEY = "claudeAiOauth"` — Claude OAuth key
- `DEFAULT_MARKETPLACE_REPO` — Claude marketplace repo

### Constants to keep in `core/constants.py`

These are genuinely shared/provider-neutral:

- `CLI_VERSION` — product version
- `CURRENT_SCHEMA_VERSION` — schema version
- `WORKTREE_BRANCH_PREFIX = "scc/"` — product-scoped git prefix
- `SAFETY_NET_POLICY_FILENAME = "effective_policy.json"` — used only by Docker Desktop sandbox (docker/launch.py), but the filename itself is provider-neutral safety-net infrastructure. Either keep in constants.py or move to docker/launch.py as a local. Moving to docker/launch.py is cleaner since it's the sole consumer.

### Guardrail test

Add a test (e.g. in `test_import_boundaries.py` or a new `test_no_claude_constants_in_shared.py`) that scans `core/constants.py` for Claude-specific constant names and fails if any are found. Alternatively, scan for known Claude-specific patterns (`claude`, `Claude`) in constant values in `core/constants.py`.

The existing `test_provider_branding.py::TestNoCloudeCodeInNonAdapterModules` pattern is the reference model for this guardrail — it scans source files and maintains an allow-list.

### OCI adapter special case

`adapters/oci_sandbox_runtime.py` imports `AGENT_NAME` and `SANDBOX_DATA_VOLUME`. For `SANDBOX_DATA_VOLUME`, it already has `spec.data_volume` from the registry (line 268: `volume_name = spec.data_volume if spec.data_volume else SANDBOX_DATA_VOLUME`). The fallback should use the Claude registry entry's data_volume instead of the shared constant. For `AGENT_NAME`, since the binary name is runner-owned (per D029 context: "No launch argv, auth fields. Launch argv is runner-owned"), it should be a local `_CLAUDE_AGENT_NAME = "claude"` in the adapter, or better yet derived from the provider — but the OCI adapter currently doesn't receive a provider_id at the `run()` call site. Simplest: define `_CLAUDE_AGENT_NAME = "claude"` locally. The adapter is Claude-only for the `cmd.extend([AGENT_NAME, ...])` path. Future multi-provider OCI launch will need to pass agent binary name via `SandboxSpec.agent_argv` (already a field).

### start_session.py special case

`start_session.py` uses `SANDBOX_IMAGE` only in the Docker Desktop sandbox fallback path (non-OCI). This is explicitly Claude-only code. Replace with a local `_DOCKER_DESKTOP_CLAUDE_IMAGE = "docker/sandbox-templates:claude-code"` or import from `docker.core` if it's defined there.

## Constraints

- No behavioral changes. This is pure import/constant cleanup.
- Existing tests must continue to pass with zero regressions.
- The `docker/` module is the Docker Desktop sandbox adapter (Claude-only). Localizing Claude constants there is the correct direction — the whole module is Claude-specific.
- The OCI adapter's `AGENT_NAME` usage is on a code path that launches `claude --dangerously-skip-permissions`. This is intentionally Claude-specific (per D033). A local constant is fine.
- `core/constants.py` docstring says "Supports multiple AI coding agents" but in practice every constant in it is Claude-specific except the product-level ones. The slice should update the docstring.

## Natural task decomposition

**T01 — Localize Claude constants in docker/ modules and update core/constants.py.** Covers docker/core.py, docker/credentials.py, docker/launch.py. Define Claude-specific constants locally in each docker module. Remove the corresponding constants from core/constants.py. Update the core/constants.py docstring. Update any test files that imported from core/constants.py for docker-related constants.

**T02 — Isolate Claude constants in OCI adapter, start_session.py, and document profile.py.** Covers adapters/oci_sandbox_runtime.py, application/start_session.py, commands/profile.py. Replace AGENT_NAME and SANDBOX_DATA_VOLUME imports in OCI adapter with local constants. Replace SANDBOX_IMAGE import in start_session.py. Add Claude-only documentation to profile.py. Update test files.

**T03 — Guardrail test and final verification.** Add a guardrail test that prevents Claude-specific runtime constants from being added back to core/constants.py. Verify no remaining shared-constant imports for Claude runtime values. Run full suite.

## Verification approach

1. `uv run pytest tests/test_docker.py tests/test_docker_core.py tests/test_docker_launch_characterization.py tests/test_docker_policy.py tests/test_docker_policy_integration.py tests/test_docker_org_config.py tests/test_oci_sandbox_runtime.py tests/test_application_start_session.py tests/test_start_session_image_routing.py -v` — all existing tests pass
2. `uv run ruff check` — no lint violations
3. `uv run mypy` on all touched files — no type errors
4. `rg 'from.*core.constants import' src/scc_cli/ -g '*.py'` — no Claude-specific constants imported from core/constants (only CLI_VERSION, CURRENT_SCHEMA_VERSION, WORKTREE_BRANCH_PREFIX remain)
5. `uv run pytest -q` — full suite passes with zero regressions
6. New guardrail test passes and would fail if a Claude constant were re-added to core/constants.py
