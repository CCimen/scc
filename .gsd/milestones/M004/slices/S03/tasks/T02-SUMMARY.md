---
id: T02
parent: S03
milestone: M004
key_files:
  - tests/fakes/fake_safety_adapter.py
  - src/scc_cli/bootstrap.py
  - tests/fakes/__init__.py
  - tests/test_safety_adapter_audit.py
key_decisions:
  - Shared engine/sink local variables in get_default_adapters() to avoid duplicate instances
  - FakeSafetyAdapter defaults to allowed/no-audit matching FakeSafetyEngine allow-all convention
duration: 
verification_result: passed
completed_at: 2026-04-04T12:47:16.191Z
blocker_discovered: false
---

# T02: Wired ClaudeSafetyAdapter and CodexSafetyAdapter into DefaultAdapters, created FakeSafetyAdapter, and added 8 integration tests covering engine → adapter → audit event chain

**Wired ClaudeSafetyAdapter and CodexSafetyAdapter into DefaultAdapters, created FakeSafetyAdapter, and added 8 integration tests covering engine → adapter → audit event chain**

## What Happened

Created FakeSafetyAdapter in tests/fakes/ with configurable result and call recording, matching the FakeSafetyEngine pattern. Extended DefaultAdapters with claude_safety_adapter and codex_safety_adapter fields (SafetyAdapter | None = None). Refactored get_default_adapters() to share engine and sink instances across safety_engine and both adapter constructors. Updated build_fake_adapters() with fake safety adapter wiring. Wrote 8 integration tests in test_safety_adapter_audit.py exercising the full engine → adapter → audit event chain for both providers, including shared-engine verdict consistency, metadata string type enforcement, and bootstrap field verification.

## Verification

All 4 verification commands passed: pytest integration tests (8/8), ruff check clean, mypy clean (257 files), full regression 3746 passed (exceeds 3726 baseline).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_safety_adapter_audit.py -v` | 0 | ✅ pass | 4200ms |
| 2 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 3 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 47000ms |
| 4 | `uv run pytest --rootdir "$PWD" -q` | 0 | ✅ pass | 43000ms |

## Deviations

Ruff import sort auto-fix needed on bootstrap.py after inserting new adapter imports — trivial, no plan impact.

## Known Issues

None.

## Files Created/Modified

- `tests/fakes/fake_safety_adapter.py`
- `src/scc_cli/bootstrap.py`
- `tests/fakes/__init__.py`
- `tests/test_safety_adapter_audit.py`
