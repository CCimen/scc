---
estimated_steps: 96
estimated_files: 10
skills_used: []
---

# T02: Create shell wrappers, update Dockerfile, add sync guardrail and integration tests

---
estimated_steps: 5
estimated_files: 11
skills_used: []
---

# T02: Create shell wrappers, update Dockerfile, add sync guardrail and integration tests

**Slice:** S02 — Runtime wrapper baseline in scc-base
**Milestone:** M004

## Description

Create the 7 shell wrapper scripts for git, curl, wget, ssh, scp, sftp, and rsync. Update the scc-base Dockerfile to install python3, COPY the evaluator and wrappers, and set PATH. Write a sync guardrail test that detects drift between evaluator copies and core originals. Write integration tests that verify the full wrapper → evaluator → verdict chain and edge cases (missing policy, malformed JSON, wrapper self-recursion prevention).

## Steps

1. Create shell wrapper scripts in `images/scc-base/wrappers/bin/` for all 7 tools: git, curl, wget, ssh, scp, sftp, rsync. Each wrapper follows this exact pattern:
   ```bash
   #!/bin/bash
   set -euo pipefail
   REAL_BIN=/usr/bin/<tool>
   EVAL_DIR="$(dirname "$(dirname "$(readlink -f "$0")")")" 
   verdict=$(python3 -m scc_safety_eval "$(basename "$0")" "$@" 2>&1) || {
     rc=$?
     if [ "$rc" -eq 2 ]; then
       echo "$verdict" >&2
       exit 2
     fi
   }
   exec "$REAL_BIN" "$@"
   ```
   The EVAL_DIR line resolves to the wrappers/ parent containing scc_safety_eval. The `PYTHONPATH` is set to include this directory so `python3 -m scc_safety_eval` works. Use absolute path for REAL_BIN to prevent self-recursion. `basename "$0"` gives the tool name (e.g. `git`).

   Important: The actual wrapper should set PYTHONPATH to `/usr/local/lib/scc` (the install location in the Dockerfile) so the evaluator package is importable. For testing outside Docker, tests will add the wrappers dir to PYTHONPATH themselves.

2. Update `images/scc-base/Dockerfile` to:
   - Add `python3` to the `apt-get install` line
   - COPY `wrappers/scc_safety_eval/` to `/usr/local/lib/scc/scc_safety_eval/`
   - COPY `wrappers/bin/` to `/usr/local/lib/scc/bin/`
   - `RUN chmod +x /usr/local/lib/scc/bin/*`
   - `ENV PYTHONPATH=/usr/local/lib/scc`
   - `ENV PATH="/usr/local/lib/scc/bin:$PATH"`

3. Write `tests/test_safety_eval_sync.py` — sync guardrail test that:
   - For each of shell_tokenizer.py, git_safety_rules.py, network_tool_rules.py: reads the core version and the evaluator copy
   - Compares them, accounting for the known import-line differences (scc_cli.core.X → relative .X)
   - After normalizing import lines, the files should be identical — if they diverge on logic, the test fails
   - This catches accidental drift when someone edits core without updating the evaluator copy

4. Write `tests/test_runtime_wrappers.py` — wrapper behavior tests that:
   - Test the evaluator CLI directly via subprocess (python3 -m scc_safety_eval) — not the shell wrappers themselves (those need Docker)
   - Test: blocked git command → exit code 2 + reason on stderr
   - Test: allowed git command → exit code 0
   - Test: network tool → exit code 2
   - Test: safe command (ls) → exit code 0
   - Test: missing SCC_POLICY_PATH → fail-closed (exit code 2 for dangerous commands)
   - Test: malformed JSON in policy file → fail-closed
   - Test: valid policy with action=allow → exit code 0
   - Add `images/scc-base/wrappers` to PYTHONPATH in subprocess env so the evaluator is importable
   - Verify shell wrapper scripts exist, are executable (file permission check), and contain the expected REAL_BIN path and anti-recursion pattern

5. Run full verification: `uv run mypy src/scc_cli`, `uv run ruff check`, `uv run pytest --rootdir "$PWD" -q`.

## Negative Tests

- **Malformed inputs**: Empty tool name to evaluator CLI, policy file with invalid JSON, policy file with wrong schema (missing 'action' key)
- **Error paths**: SCC_POLICY_PATH set to non-existent file → fail-closed block; SCC_POLICY_PATH unset → fail-closed block
- **Boundary conditions**: Command with only whitespace args; tool name with path prefix (/usr/bin/git); wrapper script targeting correct absolute binary path

## Must-Haves

- [ ] 7 shell wrapper scripts in `images/scc-base/wrappers/bin/` with correct tool names
- [ ] Each wrapper uses absolute REAL_BIN path (no self-recursion risk)
- [ ] Dockerfile installs python3, COPYs evaluator+wrappers, sets PATH and PYTHONPATH
- [ ] Sync guardrail test catches evaluator↔core drift
- [ ] Integration tests verify CLI exit codes for block/allow/fail-closed scenarios
- [ ] All 3630+ existing tests still pass; mypy and ruff clean

## Verification

```bash
# Wrapper scripts exist and are well-formed
test -f images/scc-base/wrappers/bin/git && test -f images/scc-base/wrappers/bin/curl && echo PASS

# Sync guardrail
uv run pytest tests/test_safety_eval_sync.py -v

# Runtime wrapper tests
uv run pytest tests/test_runtime_wrappers.py -v

# Type checking and lint
uv run mypy src/scc_cli
uv run ruff check

# Full regression
uv run pytest --rootdir "$PWD" -q
```

## Inputs

- `images/scc-base/wrappers/scc_safety_eval/__main__.py` — CLI entry point from T01
- `images/scc-base/wrappers/scc_safety_eval/engine.py` — standalone engine from T01
- `images/scc-base/wrappers/scc_safety_eval/policy.py` — policy loader from T01
- `images/scc-base/Dockerfile` — existing Dockerfile to update
- `src/scc_cli/core/shell_tokenizer.py` — core original for sync comparison
- `src/scc_cli/core/git_safety_rules.py` — core original for sync comparison
- `src/scc_cli/core/network_tool_rules.py` — core original for sync comparison

## Expected Output

- `images/scc-base/wrappers/bin/git` — shell wrapper
- `images/scc-base/wrappers/bin/curl` — shell wrapper
- `images/scc-base/wrappers/bin/wget` — shell wrapper
- `images/scc-base/wrappers/bin/ssh` — shell wrapper
- `images/scc-base/wrappers/bin/scp` — shell wrapper
- `images/scc-base/wrappers/bin/sftp` — shell wrapper
- `images/scc-base/wrappers/bin/rsync` — shell wrapper
- `images/scc-base/Dockerfile` — updated with python3 + wrappers
- `tests/test_safety_eval_sync.py` — sync guardrail test
- `tests/test_runtime_wrappers.py` — wrapper behavior and integration tests

## Inputs

- `images/scc-base/wrappers/scc_safety_eval/__main__.py`
- `images/scc-base/wrappers/scc_safety_eval/engine.py`
- `images/scc-base/wrappers/scc_safety_eval/policy.py`
- `images/scc-base/Dockerfile`
- `src/scc_cli/core/shell_tokenizer.py`
- `src/scc_cli/core/git_safety_rules.py`
- `src/scc_cli/core/network_tool_rules.py`

## Expected Output

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

## Verification

test -f images/scc-base/wrappers/bin/git && test -f images/scc-base/wrappers/bin/curl && test -f images/scc-base/wrappers/bin/rsync; uv run pytest tests/test_safety_eval_sync.py tests/test_runtime_wrappers.py -v; uv run mypy src/scc_cli; uv run ruff check; uv run pytest --rootdir "$PWD" -q
