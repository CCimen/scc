# S04: Error handling hardening, end-to-end verification, zero-regression gate — UAT

**Milestone:** M006-d622bc
**Written:** 2026-04-05T01:25:48.012Z

## UAT: S04 — Error handling hardening, end-to-end verification, zero-regression gate

### Preconditions
- scc-sync-1.7.3 repo checked out with S01-S04 changes
- Python 3.10+, uv installed
- Docker not required (all tests mock subprocess calls)

### Test Case 1: Session provider_id round-trip
**Steps:**
1. Run `uv run pytest tests/test_session_provider_id.py -v --no-cov`
**Expected:** 13 tests pass. SessionRecord with provider_id="codex" round-trips correctly. SessionRecord.from_dict() with missing provider_id key returns None (backward compat). SessionFilter with provider_id filters correctly.

### Test Case 2: Machine-readable provider output
**Steps:**
1. Run `uv run pytest tests/test_provider_machine_readable.py -v --no-cov`
**Expected:** 18 tests pass. build_dry_run_data() includes provider_id in output dict. build_session_list_data() includes provider_id. Support bundle manifest includes provider_id.

### Test Case 3: Container name coexistence
**Steps:**
1. Run `uv run pytest tests/test_provider_machine_readable.py::TestContainerNaming -v --no-cov`
**Expected:** Same workspace with provider_id="claude" and provider_id="codex" produces different container names. Empty provider_id preserves backward-compat hash.

### Test Case 4: Doctor provider image check
**Steps:**
1. Run `uv run pytest tests/test_doctor_image_check.py -v --no-cov`
**Expected:** 10 tests pass. Missing image returns CheckResult(passed=False) with fix_commands containing exact `docker build -t <ref> images/scc-agent-<provider>/` command. Found image returns passed=True. Unknown provider falls back to claude image ref. Subprocess failure returns graceful CheckResult.

### Test Case 5: Full coexistence proof
**Steps:**
1. Run `uv run pytest tests/test_provider_coexistence.py -v --no-cov`
**Expected:** 16 tests pass across 5 test classes:
- Container names differ per provider for same workspace
- Data volumes differ per provider
- Config dirs differ per provider
- Sessions with different provider_ids coexist and filter independently
- SandboxSpec fields (image_ref, data_volume, config_dir, agent_argv) all differ per provider

### Test Case 6: Zero-regression gate
**Steps:**
1. Run `uv run pytest --rootdir "$PWD" -q --no-cov`
2. Run `uv run ruff check`
3. Run `uv run mypy src/scc_cli`
**Expected:** 4643+ tests pass with 0 failures. Ruff reports 0 errors. Mypy reports 0 issues in 292 source files.

### Edge Cases
- **Legacy sessions without provider_id:** SessionRecord.from_dict() with dict missing provider_id key → provider_id=None, schema_version=1
- **Unknown provider in doctor check:** Falls back to claude image ref rather than crashing
- **Docker not running for image check:** Returns CheckResult(passed=False) with helpful message, does not crash
- **Empty provider_id in container naming:** Hash uses workspace-only input, preserving backward compat with pre-S04 container names
