# S05: Verification, docs truthfulness, and milestone closeout

**Goal:** All user-facing docs truthfully reflect M004 safety deliverables (core safety engine, runtime wrappers, safety-audit command, doctor safety check), guardrail tests prevent regression, and the full exit gate passes for milestone closeout.
**Demo:** After this: TBD

## Tasks
- [x] **T01: Updated README to truthfully reflect M004 safety deliverables: core safety engine, runtime wrappers, safety-audit command, and doctor safety check.** — Update README.md to truthfully reflect M004 deliverables:

1. Line 85: Update 'Command guardrails' bullet from plugin-only claim to reflect SCC-owned safety engine as the core baseline. Keep plugin mention as an additional layer. Something like: 'Command guardrails — SCC's built-in safety engine blocks destructive git commands and explicit network tools (curl, wget, ssh, scp, sftp, rsync). The scc-safety-net plugin provides additional coverage.'

2. Command table (~line 280): Add `scc support safety-audit` entry: 'Inspect recent safety-check audit events'

3. Enforcement scope section (~line 113): Add a bullet about runtime safety wrappers: 'Runtime safety: SCC-owned wrappers intercept destructive git commands and explicit network tools (curl, wget, ssh, scp, sftp, rsync) inside the container. Wrappers are defense-in-depth — topology and proxy policy remain the hard network control.'

4. Troubleshooting section (~line 382): Add mention of `scc support safety-audit` alongside launch-audit for diagnosing safety-related issues.

5. Verify no stale terms reintroduced — run existing truthfulness tests.
  - Estimate: 20m
  - Files: README.md
  - Verify: uv run pytest --rootdir "$PWD" tests/test_docs_truthfulness.py -v && grep -q 'safety-audit' README.md && grep -q 'safety engine' README.md
- [x] **T02: Added 5 safety truthfulness guardrail tests and passed the full M004 exit gate (3795 tests, ruff clean, mypy clean).** — Extend tests/test_docs_truthfulness.py with M004-specific guardrail tests:

1. test_readme_mentions_safety_audit_command — verify README contains 'safety-audit' (the new S04 command must be documented)

2. test_readme_describes_core_safety_engine — verify README mentions SCC-owned safety engine / runtime safety as a core feature (not only via plugin). Scan for pattern like 'safety engine' or 'runtime safety' in the README.

3. test_readme_enforcement_scope_mentions_runtime_wrappers — verify the enforcement scope section mentions runtime wrappers and the 7 tool families (git + curl/wget/ssh/scp/sftp/rsync)

4. test_safety_engine_core_files_exist — verify all expected core safety modules exist: safety_engine.py, shell_tokenizer.py, git_safety_rules.py, network_tool_rules.py, safety_policy_loader.py

5. test_safety_adapter_files_exist — verify both provider safety adapters exist: claude_safety_adapter.py, codex_safety_adapter.py

Then run the full exit gate:
- uv run ruff check
- uv run mypy src/scc_cli
- uv run pytest --rootdir "$PWD" -q

Confirm test count ≥ 3795 (3790 baseline + ≥5 new).
  - Estimate: 25m
  - Files: tests/test_docs_truthfulness.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest --rootdir "$PWD" -q
