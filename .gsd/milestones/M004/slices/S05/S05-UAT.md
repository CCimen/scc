# S05: Verification, docs truthfulness, and milestone closeout — UAT

**Milestone:** M004
**Written:** 2026-04-04T13:36:38.877Z

## UAT: S05 — Verification, docs truthfulness, and milestone closeout

### TC-01: README mentions safety-audit command
**Steps:** Open README.md and search for 'safety-audit'
**Expected:** The command table includes `scc support safety-audit | Inspect recent safety-check audit events`
**Result:** ✅ PASS

### TC-02: README describes core safety engine
**Steps:** Open README.md and search for 'safety engine'
**Expected:** Developer onboarding section describes SCC's built-in safety engine, not plugin-only
**Result:** ✅ PASS

### TC-03: README enforcement scope mentions runtime wrappers
**Steps:** Open README.md enforcement scope section
**Expected:** Mentions runtime wrappers as defense-in-depth for git + curl/wget/ssh/scp/sftp/rsync
**Result:** ✅ PASS

### TC-04: Guardrail tests prevent regression
**Steps:** Run `uv run pytest --rootdir "$PWD" tests/test_docs_truthfulness.py -v`
**Expected:** 10/10 tests pass (5 M003 network vocabulary + 5 M004 safety)
**Result:** ✅ PASS

### TC-05: Full exit gate
**Steps:** Run ruff, mypy, pytest
**Expected:** All clean, ≥3795 tests pass
**Result:** ✅ PASS — 3795 passed, 23 skipped, 4 xfailed
