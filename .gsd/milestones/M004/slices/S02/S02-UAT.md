# S02: Runtime wrapper baseline in `scc-base` — UAT

**Milestone:** M004
**Written:** 2026-04-04T12:29:35.228Z

## UAT: S02 — Runtime wrapper baseline in scc-base

### Preconditions
- Working directory: `scc-sync-1.7.3`
- Python environment: `uv sync` completed
- No Docker required (tests verify evaluator CLI and wrapper structure, not container runtime)

---

### TC-01: Evaluator package has zero scc_cli imports
**Steps:**
1. Run: `grep -r 'scc_cli' images/scc-base/wrappers/scc_safety_eval/`
**Expected:** Zero matches. Exit code 1 (grep found nothing).

### TC-02: Contract equivalence — blocked force push
**Steps:**
1. Run: `uv run pytest tests/test_safety_eval_contract.py::TestSafetyEvalContract::test_force_push_blocked -v`
**Expected:** Both DefaultSafetyEngine and standalone evaluator return `allowed=False`, same `matched_rule`, same `command_family=DESTRUCTIVE_GIT`.

### TC-03: Contract equivalence — safe command allowed
**Steps:**
1. Run: `uv run pytest tests/test_safety_eval_contract.py::TestSafetyEvalContract::test_safe_command_allowed -v`
**Expected:** Both engines return `allowed=True`.

### TC-04: Contract equivalence — network tool blocked
**Steps:**
1. Run: `uv run pytest tests/test_safety_eval_contract.py -k "network" -v`
**Expected:** All network tool contract tests pass — same verdicts from both engines.

### TC-05: Full contract suite
**Steps:**
1. Run: `uv run pytest tests/test_safety_eval_contract.py -v`
**Expected:** 28/28 passed.

### TC-06: CLI — blocked command exits 2
**Steps:**
1. Run: `PYTHONPATH=images/scc-base/wrappers python3 -m scc_safety_eval git push --force 2>/tmp/stderr; echo $?`
**Expected:** Exit code 2. Stderr contains block reason.

### TC-07: CLI — allowed command exits 0
**Steps:**
1. Run: `PYTHONPATH=images/scc-base/wrappers python3 -m scc_safety_eval git status 2>/dev/null; echo $?`
**Expected:** Exit code 0.

### TC-08: CLI — no args exits 2 (fail-closed)
**Steps:**
1. Run: `PYTHONPATH=images/scc-base/wrappers python3 -m scc_safety_eval 2>/dev/null; echo $?`
**Expected:** Exit code 2.

### TC-09: Fail-closed — missing SCC_POLICY_PATH
**Steps:**
1. Run: `unset SCC_POLICY_PATH; PYTHONPATH=images/scc-base/wrappers python3 -m scc_safety_eval curl https://evil.com 2>/dev/null; echo $?`
**Expected:** Exit code 2 (blocked — default fail-closed policy).

### TC-10: Fail-closed — malformed JSON policy
**Steps:**
1. Create a temp file with `{invalid json` content.
2. Run: `SCC_POLICY_PATH=/tmp/bad.json PYTHONPATH=images/scc-base/wrappers python3 -m scc_safety_eval git push --force 2>/dev/null; echo $?`
**Expected:** Exit code 2 (blocked — malformed JSON falls back to fail-closed default).

### TC-11: Policy override — action=allow
**Steps:**
1. Create a temp file: `echo '{"action": "allow", "rules": {}}' > /tmp/allow.json`
2. Run: `SCC_POLICY_PATH=/tmp/allow.json PYTHONPATH=images/scc-base/wrappers python3 -m scc_safety_eval git push --force 2>/dev/null; echo $?`
**Expected:** Exit code 0 (allowed — policy action=allow overrides).

### TC-12: All 7 wrapper scripts exist and are executable
**Steps:**
1. For each of git, curl, wget, ssh, scp, sftp, rsync:
   - Run: `test -f images/scc-base/wrappers/bin/<tool> && test -x images/scc-base/wrappers/bin/<tool>`
**Expected:** All 7 pass.

### TC-13: Wrapper scripts use absolute REAL_BIN
**Steps:**
1. Run: `grep -c 'REAL_BIN=/usr/bin/' images/scc-base/wrappers/bin/*`
**Expected:** Each file contains exactly one REAL_BIN=/usr/bin/<tool> line.

### TC-14: Wrapper scripts use basename for tool name
**Steps:**
1. Run: `grep 'basename.*\$0' images/scc-base/wrappers/bin/git`
**Expected:** Line present using `basename "$0"` for tool name.

### TC-15: Sync guardrail — core↔evaluator drift detection
**Steps:**
1. Run: `uv run pytest tests/test_safety_eval_sync.py -v`
**Expected:** 3/3 passed — shell_tokenizer, git_safety_rules, and network_tool_rules match core after import normalization.

### TC-16: Dockerfile includes python3 and wrapper setup
**Steps:**
1. Run: `grep 'python3' images/scc-base/Dockerfile`
2. Run: `grep 'PYTHONPATH=/usr/local/lib/scc' images/scc-base/Dockerfile`
3. Run: `grep '/usr/local/lib/scc/bin' images/scc-base/Dockerfile`
**Expected:** All three patterns present.

### TC-17: Full integration test suite
**Steps:**
1. Run: `uv run pytest tests/test_runtime_wrappers.py -v`
**Expected:** All tests pass (68 tests covering structural checks, CLI behavior, fail-closed, and policy overrides).

### TC-18: Full regression — no existing tests broken
**Steps:**
1. Run: `uv run pytest --rootdir "$PWD" -q`
**Expected:** 3726 passed, 23 skipped, 4 xfailed. Zero failures.

### TC-19: Lint and type-check clean
**Steps:**
1. Run: `uv run ruff check`
2. Run: `uv run mypy src/scc_cli`
**Expected:** Both clean — no errors.

### Edge Cases

### TC-20: Empty tool name
**Steps:**
1. Run: `PYTHONPATH=images/scc-base/wrappers python3 -m scc_safety_eval "" 2>/dev/null; echo $?`
**Expected:** Exit code 0 or 2 (empty command is not dangerous — either pass-through or fail-closed, both are acceptable).

### TC-21: Tool name with path prefix
**Steps:**
1. Run: `PYTHONPATH=images/scc-base/wrappers python3 -m scc_safety_eval /usr/bin/git push --force 2>/dev/null; echo $?`
**Expected:** Exit code 2 if evaluator strips the path prefix, or exit code 0 if it treats `/usr/bin/git` as a non-matching tool name. Integration tests document the actual behavior.
