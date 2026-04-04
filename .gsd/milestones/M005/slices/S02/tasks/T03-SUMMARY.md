---
id: T03
parent: S02
milestone: M005
key_files:
  - src/scc_cli/docker/sandbox.py
  - src/scc_cli/docker/launch.py
  - src/scc_cli/marketplace/materialize_git.py
  - src/scc_cli/marketplace/materialize.py
  - tests/test_docker_launch_characterization.py
  - tests/test_plugin_isolation.py
key_decisions:
  - Used deferred imports in sandbox.py run_sandbox for launch.py functions to preserve test-patch compatibility
  - Replaced err_line with logging.getLogger(__name__).warning() to eliminate docker→presentation boundary violation
  - Module-level imports for credentials.py functions in sandbox.py with updated test patch targets
duration: 
verification_result: passed
completed_at: 2026-04-04T15:41:10.979Z
blocker_discovered: false
---

# T03: Extracted sandbox runtime functions from docker/launch.py (874→498 lines) and git/download operations from marketplace/materialize.py (866→612 lines), eliminating docker→presentation console.err_line boundary violation

**Extracted sandbox runtime functions from docker/launch.py (874→498 lines) and git/download operations from marketplace/materialize.py (866→612 lines), eliminating docker→presentation console.err_line boundary violation**

## What Happened

Decomposed two oversized modules into focused extraction files. docker/launch.py → docker/sandbox.py: extracted run_sandbox (218L), inject_plugin_settings_to_container (67L), seed_container_plugin_marketplaces (41L), _build_known_marketplaces_cache (31L), and _is_mount_race_error (19L). Replaced 4 err_line calls with logging.warning() to fix the docker→presentation boundary violation. marketplace/materialize.py → marketplace/materialize_git.py: extracted run_git_clone (84L), download_and_extract (120L), _discover_plugins (35L), and CloneResult/DownloadResult/DiscoveryResult dataclasses. All moved names re-exported from residual modules for backward compatibility. Updated test patch targets in test_docker_launch_characterization.py and test_plugin_isolation.py.

## Verification

All must-haves verified: docker/launch.py at 498 lines (<800), marketplace/materialize.py at 612 lines (<800), no console.err_line import in docker/, 27 docker launch characterization tests pass, 24 marketplace materialize tests pass, 31 import boundary tests pass, ruff check and mypy clean, full suite 4079 passed with 0 failures.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 7600ms |
| 2 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 7600ms |
| 3 | `uv run pytest tests/test_docker_launch_characterization.py tests/test_marketplace_materialize_characterization.py tests/test_import_boundaries.py -q` | 0 | ✅ pass (82 tests) | 1950ms |
| 4 | `uv run pytest -q` | 0 | ✅ pass (4079 tests) | 65680ms |

## Deviations

Updated tests/test_plugin_isolation.py patch targets (not mentioned in plan) — this test patched scc_cli.docker.launch.build_command and subprocess.run which needed updating. Kept reset_global_settings in launch.py and used deferred imports in sandbox.py for test-patch compatibility.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/docker/sandbox.py`
- `src/scc_cli/docker/launch.py`
- `src/scc_cli/marketplace/materialize_git.py`
- `src/scc_cli/marketplace/materialize.py`
- `tests/test_docker_launch_characterization.py`
- `tests/test_plugin_isolation.py`
