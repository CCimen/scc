---
id: T02
parent: S02
milestone: M004
key_files:
  - images/scc-base/wrappers/bin/git
  - images/scc-base/wrappers/bin/curl
  - images/scc-base/wrappers/bin/wget
  - images/scc-base/wrappers/bin/ssh
  - images/scc-base/wrappers/bin/scp
  - images/scc-base/wrappers/bin/sftp
  - images/scc-base/wrappers/bin/rsync
  - images/scc-base/Dockerfile
  - tests/test_safety_eval_sync.py
  - tests/test_runtime_wrappers.py
key_decisions:
  - Added per-file-ignores for images/**/scc_safety_eval/*.py to allow T201 (print to stderr is the evaluator's sole output mechanism)
  - Shell wrappers use absolute REAL_BIN=/usr/bin/<tool> to prevent self-recursion
  - Added wget/openssh-client/rsync to Dockerfile apt-get to provide real binaries for wrapped tools
duration: 
verification_result: passed
completed_at: 2026-04-04T12:24:03.717Z
blocker_discovered: false
---

# T02: Created 7 shell wrappers, updated scc-base Dockerfile with python3 + evaluator install, and added 71 tests (sync guardrail + integration) — all passing alongside 3726 existing tests

**Created 7 shell wrappers, updated scc-base Dockerfile with python3 + evaluator install, and added 71 tests (sync guardrail + integration) — all passing alongside 3726 existing tests**

## What Happened

Created 7 shell wrapper scripts in images/scc-base/wrappers/bin/ with anti-recursion pattern (absolute REAL_BIN, basename $0). Updated scc-base Dockerfile to install python3, copy evaluator and wrappers to /usr/local/lib/scc/, and set PATH/PYTHONPATH. Wrote sync guardrail test (3 tests) comparing core↔evaluator module copies with import normalization. Wrote integration tests (68 tests) covering wrapper structural checks, blocked/allowed commands, fail-closed behavior, policy overrides, and negative cases. Also fixed ruff T201 violations and import sorting from T01.

## Verification

All verification gates passed: ruff check clean, mypy clean (254 files), 68 new tests pass, 28 contract tests pass, full regression 3726 passed (23 skipped, 4 xfailed), no scc_cli imports in evaluator package.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 2000ms |
| 2 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 3 | `uv run pytest tests/test_safety_eval_sync.py tests/test_runtime_wrappers.py -v` | 0 | ✅ pass | 1500ms |
| 4 | `uv run pytest tests/test_safety_eval_contract.py -v` | 0 | ✅ pass | 1500ms |
| 5 | `uv run pytest --rootdir $PWD -q` | 0 | ✅ pass | 43000ms |
| 6 | `grep -r scc_cli images/scc-base/wrappers/scc_safety_eval/ && echo FAIL || echo PASS` | 0 | ✅ pass | 100ms |

## Deviations

Fixed ruff T201 violations in evaluator package from T01 by adding per-file-ignores. Fixed unused pytest import and import sorting in test_safety_eval_contract.py. Added wget/openssh-client/rsync to Dockerfile apt-get install. Fixed one test to check stderr instead of stdout for block reasons.

## Known Issues

None.

## Files Created/Modified

- `images/scc-base/wrappers/bin/git`
- `images/scc-base/wrappers/bin/curl`
- `images/scc-base/wrappers/bin/wget`
- `images/scc-base/wrappers/bin/ssh`
- `images/scc-base/wrappers/bin/scp`
- `images/scc-base/wrappers/bin/sftp`
- `images/scc-base/wrappers/bin/rsync`
- `images/scc-base/Dockerfile`
- `tests/test_safety_eval_sync.py`
- `tests/test_runtime_wrappers.py`
