---
id: T01
parent: S05
milestone: M002
key_files:
  - src/scc_cli/application/launch/audit_log.py
  - src/scc_cli/application/support_bundle.py
  - src/scc_cli/commands/support.py
  - src/scc_cli/kinds.py
  - src/scc_cli/presentation/json/launch_audit_json.py
  - tests/test_launch_audit_support.py
  - tests/test_support_bundle.py
  - README.md
key_decisions:
  - Use one application-level launch-audit reader for both the support CLI surface and support-bundle enrichment.
  - Keep launch-audit inspection bounded to recent tailed lines from the append-only JSONL sink rather than inventing a second persisted diagnostics format.
duration: 
verification_result: passed
completed_at: 2026-04-03T20:59:29.271Z
blocker_discovered: false
---

# T01: Added `scc support launch-audit` and redacted recent launch-audit summaries in support bundles.

**Added `scc support launch-audit` and redacted recent launch-audit summaries in support bundles.**

## What Happened

Added `src/scc_cli/application/launch/audit_log.py` as the bounded, redaction-safe reader for the durable launch-audit JSONL sink, then reused it from the new `scc support launch-audit` command and the support-bundle manifest path. The new diagnostics surface reports recent events, malformed-record counts, sink destination, and last-failure context in both human and stable JSON-envelope forms. Support-bundle manifests now include a bounded `launch_audit` section that survives unrelated collection failures, and README command/troubleshooting guidance now points operators to the new inspection path.

## Verification

Ran the slice verification command `uv run pytest --rootdir . ./tests/test_launch_audit_support.py ./tests/test_support_bundle.py -q` and confirmed 35 focused tests passed. Ran `uv run ruff check`, `uv run mypy src/scc_cli`, and `uv run pytest`; all passed, including the full suite (`3283 passed, 23 skipped, 4 xfailed`).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest --rootdir . ./tests/test_launch_audit_support.py ./tests/test_support_bundle.py -q` | 0 | ✅ pass | 4959ms |
| 2 | `uv run ruff check` | 0 | ✅ pass | 39ms |
| 3 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 6732ms |
| 4 | `uv run pytest` | 0 | ✅ pass | 39300ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/application/launch/audit_log.py`
- `src/scc_cli/application/support_bundle.py`
- `src/scc_cli/commands/support.py`
- `src/scc_cli/kinds.py`
- `src/scc_cli/presentation/json/launch_audit_json.py`
- `tests/test_launch_audit_support.py`
- `tests/test_support_bundle.py`
- `README.md`
