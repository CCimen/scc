---
id: T02
parent: S01
milestone: M008-g7jk8d
key_files:
  - src/scc_cli/commands/launch/preflight.py
  - tests/test_launch_preflight.py
key_decisions:
  - Deferred imports for ensure_provider_image to keep preflight.py free of subprocess at module level
  - _infer_resolution_source mirrors choose_start_provider precedence rather than modifying it
duration: 
verification_result: passed
completed_at: 2026-04-06T12:12:16.947Z
blocker_discovered: false
---

# T02: Created commands/launch/preflight.py with typed LaunchReadiness model and three-function preflight split (resolve → collect → ensure), verified by 39 new tests

**Created commands/launch/preflight.py with typed LaunchReadiness model and three-function preflight split (resolve → collect → ensure), verified by 39 new tests**

## What Happened

Built src/scc_cli/commands/launch/preflight.py with the full typed readiness model: ImageStatus, AuthStatus, ProviderResolutionSource enums and a frozen LaunchReadiness dataclass. The module implements the three-function split: (1) allowed_provider_ids() — pure team policy extraction, (2) resolve_launch_provider() — wraps choose_start_provider() with source tracking via ProviderResolutionSource, (3) collect_launch_readiness() — reads image and auth state from adapters into the typed model, (4) ensure_launch_ready() — fixes gaps using ensure_provider_image and auth bootstrap, or raises ProviderNotReadyError in non-interactive mode. Added 39 new tests across 9 test classes covering all public functions and edge cases.

## Verification

All 51 tests in test_launch_preflight.py pass (12 existing + 39 new). ruff check clean. mypy clean. Full suite: 4960 passed with same 26 pre-existing failures — no regressions.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_launch_preflight.py -v` | 0 | ✅ pass | 1200ms |
| 2 | `uv run ruff check src/scc_cli/commands/launch/preflight.py` | 0 | ✅ pass | 2400ms |
| 3 | `uv run mypy src/scc_cli/commands/launch/preflight.py` | 0 | ✅ pass | 2400ms |
| 4 | `uv run pytest` | 1 | ✅ pass (pre-existing failures only, 4960 passed) | 65000ms |

## Deviations

Used deferred imports inside ensure_launch_ready() and _check_image_available() for subprocess-heavy modules; patched original module paths in tests accordingly. _ensure_auth delegates via show_notice callback rather than calling provider.bootstrap_auth() directly.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/commands/launch/preflight.py`
- `tests/test_launch_preflight.py`
