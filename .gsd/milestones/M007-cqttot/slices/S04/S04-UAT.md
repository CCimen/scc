# S04: Legacy Claude path isolation and Docker module cleanup — UAT

**Milestone:** M007-cqttot
**Written:** 2026-04-05T14:06:37.172Z

## UAT: Legacy Claude path isolation and Docker module cleanup

### Preconditions
- Working checkout of scc-sync-1.7.3 with S04 changes applied
- Python 3.10+, uv installed, `uv sync` completed

### Test 1: core/constants.py contains only product-level constants
**Steps:**
1. Open `src/scc_cli/core/constants.py`
2. Verify the file defines exactly: `WORKTREE_BRANCH_PREFIX`, `_FALLBACK_VERSION`, `_get_version()`, `CLI_VERSION`, `CURRENT_SCHEMA_VERSION`
3. Verify no occurrence of: AGENT_NAME, SANDBOX_IMAGE, AGENT_CONFIG_DIR, SANDBOX_DATA_VOLUME, SANDBOX_DATA_MOUNT, CREDENTIAL_PATHS, OAUTH_CREDENTIAL_KEY, DEFAULT_MARKETPLACE_REPO, SAFETY_NET_POLICY_FILENAME

**Expected:** File is 49 lines. Module docstring says "Product-level constants for SCC-CLI." No Claude-specific values present.

### Test 2: docker/ modules define their own constants
**Steps:**
1. `grep -n '_SANDBOX_IMAGE\|_SANDBOX_DATA_MOUNT' src/scc_cli/docker/core.py` — expect lines 30-31
2. `grep -n '_OAUTH_CREDENTIAL_KEY\|_SANDBOX_DATA_VOLUME' src/scc_cli/docker/credentials.py` — expect lines 35-36
3. `grep -n '_SAFETY_NET_POLICY_FILENAME\|_SANDBOX_DATA_MOUNT\|_SANDBOX_DATA_VOLUME' src/scc_cli/docker/launch.py` — expect lines near top of file
4. Verify none of these files import from `core.constants`

**Expected:** Each file has module-level `_` prefixed constants with the correct Claude-specific values. No `from ..core.constants import` lines.

### Test 3: OCI adapter and start_session use _CLAUDE_* prefixed constants
**Steps:**
1. `grep -n '_CLAUDE_AGENT_NAME\|_CLAUDE_DATA_VOLUME' src/scc_cli/adapters/oci_sandbox_runtime.py` — expect lines 45-46
2. `grep -n '_DOCKER_DESKTOP_CLAUDE_IMAGE' src/scc_cli/application/start_session.py` — expect line 40
3. Verify neither file imports from `core.constants` for Claude values

**Expected:** Self-documenting constant names with _CLAUDE_ prefix. No core.constants Claude imports.

### Test 4: profile.py documented as Claude-only
**Steps:**
1. Read the first 10 lines of `src/scc_cli/commands/profile.py`
2. Check docstring mentions "Claude provider only" and explains the hardcoded `.claude/settings.local.json` references

**Expected:** Module docstring explicitly says "Claude provider only" with rationale.

### Test 5: Guardrail test catches re-introduction
**Steps:**
1. `uv run pytest tests/test_no_claude_constants_in_core.py -v`
2. Temporarily add `SANDBOX_IMAGE = "test"` to core/constants.py
3. Rerun — should fail with actionable message
4. Revert the change

**Expected:** Step 1 passes (2/2). Step 3 fails with message naming the constant and line. Step 4 restores clean state.

### Test 6: Zero Claude-constant imports from core.constants across codebase
**Steps:**
1. `rg 'from.*core\.constants import.*(AGENT_NAME|SANDBOX_IMAGE|SANDBOX_DATA_VOLUME|SANDBOX_DATA_MOUNT|OAUTH_CREDENTIAL_KEY|AGENT_CONFIG_DIR|CREDENTIAL_PATHS|DEFAULT_MARKETPLACE_REPO|SAFETY_NET_POLICY_FILENAME)' src/scc_cli/`

**Expected:** No output (exit code 1 = no matches).

### Test 7: Full test suite regression check
**Steps:**
1. `uv run pytest -q`

**Expected:** 4720 passed, 23 skipped, 2 xfailed. Zero failures.

### Test 8: Lint and type check clean
**Steps:**
1. `uv run ruff check`
2. `uv run mypy src/scc_cli`

**Expected:** Both exit 0 with no errors.

### Edge Cases
- **New developer adds Claude constant to core/constants.py:** Caught by test_no_claude_constants_defined_in_core (tokenize-based scan)
- **New module imports a Claude constant from core.constants:** Caught by test_no_claude_constant_imports_from_core (codebase-wide scan)
- **Comment or docstring mentioning SANDBOX_IMAGE in core/constants.py:** Not flagged (tokenize correctly ignores non-NAME tokens)
