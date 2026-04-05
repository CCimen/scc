---
id: T02
parent: S05
milestone: M007-cqttot
key_files:
  - src/scc_cli/core/contracts.py
  - src/scc_cli/core/provider_registry.py
  - src/scc_cli/adapters/oci_sandbox_runtime.py
  - src/scc_cli/application/start_session.py
  - tests/test_provider_registry.py
  - tests/test_oci_sandbox_runtime.py
key_decisions:
  - Use settings_scope field on ProviderRuntimeSpec rather than separate path resolution logic
  - Use .git/info/exclude (local, untracked) instead of .gitignore for repo cleanliness
  - Best-effort git exclude — failures non-fatal to avoid blocking agent launch
duration: 
verification_result: passed
completed_at: 2026-04-05T14:33:35.379Z
blocker_discovered: false
---

# T02: Added workspace-scoped Codex settings path and git-exclude repo cleanliness for D041 config ownership layering

**Added workspace-scoped Codex settings path and git-exclude repo cleanliness for D041 config ownership layering**

## What Happened

Implemented D041: Codex SCC-managed config now uses workspace-scoped .codex/config.toml instead of home-level /home/agent/.codex/config.toml. Added settings_scope field to ProviderRuntimeSpec (default "home", Codex set to "workspace"). Updated _build_agent_settings() to route by scope and _inject_settings() to create workspace config dirs and exclude them via .git/info/exclude. Added 6 new tests covering scope values, git exclude behavior, and cp target paths.

## Verification

uv run ruff check — zero errors. uv run mypy src/scc_cli — 0 issues in 293 files. uv run pytest tests/test_provider_registry.py tests/test_oci_sandbox_runtime.py -v — 66 passed. uv run pytest -q — 4731 passed, 0 failed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 57000ms |
| 2 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 57000ms |
| 3 | `uv run pytest tests/test_provider_registry.py tests/test_oci_sandbox_runtime.py -v` | 0 | ✅ pass | 6000ms |
| 4 | `uv run pytest tests/test_docs_truthfulness.py tests/test_provider_branding.py -v` | 0 | ✅ pass | 6000ms |
| 5 | `uv run pytest -q` | 0 | ✅ pass | 56000ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/core/contracts.py`
- `src/scc_cli/core/provider_registry.py`
- `src/scc_cli/adapters/oci_sandbox_runtime.py`
- `src/scc_cli/application/start_session.py`
- `tests/test_provider_registry.py`
- `tests/test_oci_sandbox_runtime.py`
