# S02: Runtime wrapper baseline in `scc-base`

**Goal:** Runtime wrappers for exactly 7 tools (git, curl, wget, ssh, scp, sftp, rsync) exist in the scc-base image layout, powered by a standalone Python evaluator that produces identical verdicts to DefaultSafetyEngine. Wrappers are fail-closed without policy.
**Demo:** After this: TBD

## Tasks
- [x] **T01: Created standalone scc_safety_eval package (9 files, stdlib-only) with 28 contract tests proving identical verdicts to DefaultSafetyEngine** — ---
estimated_steps: 5
estimated_files: 10
skills_used: []
---

# T01: Create standalone safety evaluator package with contract tests

**Slice:** S02 — Runtime wrapper baseline in scc-base
**Milestone:** M004

## Description

Create the standalone Python evaluator package at `images/scc-base/wrappers/scc_safety_eval/` that embeds the safety logic from S01's core modules. The evaluator must produce identical verdicts to `DefaultSafetyEngine` for the same inputs, using only Python 3 stdlib (no scc_cli dependency). Write contract tests that feed identical inputs to both `DefaultSafetyEngine` and the standalone evaluator and assert identical results.

The evaluator package contains adapted copies of 4 core modules (shell_tokenizer, git_safety_rules, network_tool_rules, contracts/enums combined) plus new files: engine.py (orchestrator), policy.py (policy loader from SCC_POLICY_PATH), and __main__.py (CLI entry point).

All `scc_cli.core.*` imports must be replaced with relative imports within the package. Only `SafetyPolicy`, `SafetyVerdict` from contracts and `CommandFamily` from enums are needed.

## Steps

1. Create `images/scc-base/wrappers/scc_safety_eval/__init__.py` (empty package marker).

2. Create `images/scc-base/wrappers/scc_safety_eval/contracts.py` — stripped-down version containing only `SafetyPolicy` and `SafetyVerdict` dataclasses. Remove all other types (DestinationSet, EgressRule, etc.). Remove the `from .enums import NetworkPolicy, SeverityLevel` import. Keep `from dataclasses import dataclass, field` and `from typing import Any`.

3. Create `images/scc-base/wrappers/scc_safety_eval/enums.py` — stripped-down version containing only `CommandFamily(str, Enum)`. Remove all other enums.

4. Create `images/scc-base/wrappers/scc_safety_eval/shell_tokenizer.py` — copy of `src/scc_cli/core/shell_tokenizer.py` verbatim (no scc_cli imports in this file — it only uses stdlib).

5. Create `images/scc-base/wrappers/scc_safety_eval/git_safety_rules.py` — copy of `src/scc_cli/core/git_safety_rules.py` with imports changed from `from scc_cli.core.contracts import SafetyVerdict` to `from .contracts import SafetyVerdict` and `from scc_cli.core.enums import CommandFamily` to `from .enums import CommandFamily`.

6. Create `images/scc-base/wrappers/scc_safety_eval/network_tool_rules.py` — copy of `src/scc_cli/core/network_tool_rules.py` with imports changed from `from scc_cli.core.contracts import SafetyVerdict` to `from .contracts import SafetyVerdict` and `from scc_cli.core.enums import CommandFamily` to `from .enums import CommandFamily`.

7. Create `images/scc-base/wrappers/scc_safety_eval/engine.py` — adapted version of `src/scc_cli/core/safety_engine.py` with all `scc_cli.core.*` imports replaced by relative imports (`.contracts`, `.git_safety_rules`, `.network_tool_rules`, `.shell_tokenizer`). Keep the `DefaultSafetyEngine` class and all logic identical.

8. Create `images/scc-base/wrappers/scc_safety_eval/policy.py` — policy loader that reads `$SCC_POLICY_PATH` environment variable. If unset or file missing, return a fail-closed default policy (`SafetyPolicy(action='block', rules={})`). If file exists, parse JSON and construct `SafetyPolicy`. Handle malformed JSON by returning the fail-closed default (never fail-open).

9. Create `images/scc-base/wrappers/scc_safety_eval/__main__.py` — CLI entry point:
   - Usage: `python3 -m scc_safety_eval <tool> [args...]`
   - Load policy via `policy.py`
   - Reconstruct the command string from sys.argv (tool name + args)
   - Evaluate using the engine
   - Exit 0 if allowed, exit 2 with reason on stderr if blocked
   - Handle any unexpected exceptions by exiting 2 (fail-closed)

10. Write `tests/test_safety_eval_contract.py` — contract tests that:
    - Import both `DefaultSafetyEngine` from `scc_cli.core.safety_engine` and the standalone engine from `scc_safety_eval.engine`
    - Feed identical command/policy pairs to both engines
    - Assert `verdict.allowed`, `verdict.matched_rule`, and `verdict.command_family` match for each pair
    - Test cases: force push blocked, network tool blocked, safe command allowed, warn mode, disabled rule, nested bash -c, empty command, allow policy bypass
    - Add `images/scc-base/wrappers` to sys.path in the test file so the standalone package is importable

## Must-Haves

- [ ] All 8 package files exist under `images/scc-base/wrappers/scc_safety_eval/`
- [ ] Zero `scc_cli` imports in the evaluator package — only stdlib and relative imports
- [ ] Policy loader returns fail-closed default when SCC_POLICY_PATH is unset, file missing, or JSON malformed
- [ ] CLI entry point exits 0 for allowed, 2 for blocked, 2 for unexpected errors
- [ ] Contract tests pass proving verdict equivalence with DefaultSafetyEngine

## Verification

```bash
# Verify no scc_cli imports in evaluator package
grep -r 'scc_cli' images/scc-base/wrappers/scc_safety_eval/ && echo FAIL || echo PASS

# Contract tests
uv run pytest tests/test_safety_eval_contract.py -v

# Existing tests still pass
uv run pytest --rootdir "$PWD" -q
```

## Inputs

- `src/scc_cli/core/shell_tokenizer.py` — source module to copy verbatim
- `src/scc_cli/core/git_safety_rules.py` — source module to adapt imports
- `src/scc_cli/core/network_tool_rules.py` — source module to adapt imports
- `src/scc_cli/core/safety_engine.py` — source module to adapt imports
- `src/scc_cli/core/contracts.py` — source for SafetyPolicy and SafetyVerdict extraction
- `src/scc_cli/core/enums.py` — source for CommandFamily extraction

## Expected Output

- `images/scc-base/wrappers/scc_safety_eval/__init__.py` — package marker
- `images/scc-base/wrappers/scc_safety_eval/contracts.py` — stripped SafetyPolicy + SafetyVerdict
- `images/scc-base/wrappers/scc_safety_eval/enums.py` — stripped CommandFamily enum
- `images/scc-base/wrappers/scc_safety_eval/shell_tokenizer.py` — verbatim copy
- `images/scc-base/wrappers/scc_safety_eval/git_safety_rules.py` — adapted imports
- `images/scc-base/wrappers/scc_safety_eval/network_tool_rules.py` — adapted imports
- `images/scc-base/wrappers/scc_safety_eval/engine.py` — adapted orchestrator
- `images/scc-base/wrappers/scc_safety_eval/policy.py` — policy loader
- `images/scc-base/wrappers/scc_safety_eval/__main__.py` — CLI entry point
- `tests/test_safety_eval_contract.py` — contract tests
  - Estimate: 1h30m
  - Files: images/scc-base/wrappers/scc_safety_eval/__init__.py, images/scc-base/wrappers/scc_safety_eval/contracts.py, images/scc-base/wrappers/scc_safety_eval/enums.py, images/scc-base/wrappers/scc_safety_eval/shell_tokenizer.py, images/scc-base/wrappers/scc_safety_eval/git_safety_rules.py, images/scc-base/wrappers/scc_safety_eval/network_tool_rules.py, images/scc-base/wrappers/scc_safety_eval/engine.py, images/scc-base/wrappers/scc_safety_eval/policy.py, images/scc-base/wrappers/scc_safety_eval/__main__.py, tests/test_safety_eval_contract.py
  - Verify: grep -r 'scc_cli' images/scc-base/wrappers/scc_safety_eval/ && exit 1 || true; uv run pytest tests/test_safety_eval_contract.py -v; uv run pytest --rootdir "$PWD" -q
- [x] **T02: Created 7 shell wrappers, updated scc-base Dockerfile with python3 + evaluator install, and added 71 tests (sync guardrail + integration) — all passing alongside 3726 existing tests** — ---
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
  - Estimate: 1h
  - Files: images/scc-base/wrappers/bin/git, images/scc-base/wrappers/bin/curl, images/scc-base/wrappers/bin/wget, images/scc-base/wrappers/bin/ssh, images/scc-base/wrappers/bin/scp, images/scc-base/wrappers/bin/sftp, images/scc-base/wrappers/bin/rsync, images/scc-base/Dockerfile, tests/test_safety_eval_sync.py, tests/test_runtime_wrappers.py
  - Verify: test -f images/scc-base/wrappers/bin/git && test -f images/scc-base/wrappers/bin/curl && test -f images/scc-base/wrappers/bin/rsync; uv run pytest tests/test_safety_eval_sync.py tests/test_runtime_wrappers.py -v; uv run mypy src/scc_cli; uv run ruff check; uv run pytest --rootdir "$PWD" -q
