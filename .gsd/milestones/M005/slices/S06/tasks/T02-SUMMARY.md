---
id: T02
parent: S06
milestone: M005
key_files:
  - src/scc_cli/adapters/codex_agent_provider.py
  - src/scc_cli/adapters/codex_renderer.py
  - src/scc_cli/adapters/claude_renderer.py
  - src/scc_cli/core/bundle_resolver.py
  - src/scc_cli/doctor/checks/artifacts.py
  - src/scc_cli/application/start_session.py
  - src/scc_cli/schemas/org-v1.schema.json
  - tests/test_docs_truthfulness.py
  - tests/test_file_sizes.py
key_decisions:
  - Codex capability_profile updated to supports_skills=True and supports_native_integrations=True to match renderer implementation
  - Portable artifacts without bindings are 'policy-effective' not 'renderable' — resolver comment updated
  - sync_marketplace_settings_for_start marked as transitional; bundle pipeline is canonical
  - Use NormalizedOrgConfig.from_dict() to avoid import boundary violation from doctor to adapters
duration: 
verification_result: passed
completed_at: 2026-04-04T20:49:31.529Z
blocker_discovered: false
---

# T02: Fixed four truthfulness gaps: Codex capability_profile, portable-artifact contract mismatch, renderer overclaiming, and transitional marketplace sync; added governed_artifacts/enabled_bundles to schema; removed stale xfail; fixed import boundary violation

**Fixed four truthfulness gaps: Codex capability_profile, portable-artifact contract mismatch, renderer overclaiming, and transitional marketplace sync; added governed_artifacts/enabled_bundles to schema; removed stale xfail; fixed import boundary violation**

## What Happened

Addressed four specific truthfulness gaps: (1) Updated bundle resolver comment to honestly describe portable artifacts without bindings as 'policy-effective' not 'renderable'; (2) Set Codex capability_profile supports_skills=True and supports_native_integrations=True; (3) Updated both renderer module docstrings to say 'metadata-only' for native integration output; (4) Marked sync_marketplace_settings_for_start as transitional. Also fixed import boundary violation in doctor/checks/artifacts.py, removed stale xfail on test_file_size_limits, updated org-v1.schema.json with governed_artifacts and enabled_bundles, and added 8 truthfulness guardrail tests.

## Verification

All three verification gates pass: ruff check (0 errors), mypy (0 issues in 289 files), full pytest suite (4462 passed, 0 failed, 0 xpassed, 23 skipped, 3 xfailed). Truthfulness tests (18/18), import boundaries (31/31), file sizes (1/1 without xfail).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 3000ms |
| 2 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3500ms |
| 3 | `uv run pytest tests/test_docs_truthfulness.py -v` | 0 | ✅ pass (18/18) | 1600ms |
| 4 | `uv run pytest tests/test_import_boundaries.py -v` | 0 | ✅ pass (31/31) | 1900ms |
| 5 | `uv run pytest tests/test_file_sizes.py -v` | 0 | ✅ pass (1/1) | 1200ms |
| 6 | `uv run pytest --rootdir "$PWD" -q` | 0 | ✅ pass (4462 passed) | 72000ms |

## Deviations

Fixed import boundary violation in doctor/checks/artifacts.py from T01 — replaced direct scc_cli.adapters.config_normalizer import with NormalizedOrgConfig.from_dict(). Removed stale xfail on test_file_size_limits.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/adapters/codex_agent_provider.py`
- `src/scc_cli/adapters/codex_renderer.py`
- `src/scc_cli/adapters/claude_renderer.py`
- `src/scc_cli/core/bundle_resolver.py`
- `src/scc_cli/doctor/checks/artifacts.py`
- `src/scc_cli/application/start_session.py`
- `src/scc_cli/schemas/org-v1.schema.json`
- `tests/test_docs_truthfulness.py`
- `tests/test_file_sizes.py`
