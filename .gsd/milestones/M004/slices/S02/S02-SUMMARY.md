---
id: S02
parent: M004
milestone: M004
provides:
  - Standalone scc_safety_eval package in images/scc-base/wrappers/ for container image builds
  - 7 shell wrapper scripts in images/scc-base/wrappers/bin/ for PATH-first interception
  - Updated scc-base Dockerfile with python3 + evaluator + wrappers installed
  - Contract test suite proving evaluator↔engine verdict equivalence
  - Sync-guardrail test catching core↔evaluator drift
requires:
  - slice: S01
    provides: DefaultSafetyEngine, SafetyPolicy, SafetyVerdict, CommandFamily, shell_tokenizer, git_safety_rules, network_tool_rules
affects:
  - S03
  - S04
  - S05
key_files:
  - images/scc-base/wrappers/scc_safety_eval/engine.py
  - images/scc-base/wrappers/scc_safety_eval/policy.py
  - images/scc-base/wrappers/scc_safety_eval/__main__.py
  - images/scc-base/wrappers/scc_safety_eval/contracts.py
  - images/scc-base/wrappers/scc_safety_eval/enums.py
  - images/scc-base/wrappers/scc_safety_eval/shell_tokenizer.py
  - images/scc-base/wrappers/scc_safety_eval/git_safety_rules.py
  - images/scc-base/wrappers/scc_safety_eval/network_tool_rules.py
  - images/scc-base/wrappers/bin/git
  - images/scc-base/wrappers/bin/curl
  - images/scc-base/wrappers/bin/wget
  - images/scc-base/wrappers/bin/ssh
  - images/scc-base/wrappers/bin/scp
  - images/scc-base/wrappers/bin/sftp
  - images/scc-base/wrappers/bin/rsync
  - images/scc-base/Dockerfile
  - tests/test_safety_eval_contract.py
  - tests/test_safety_eval_sync.py
  - tests/test_runtime_wrappers.py
key_decisions:
  - Standalone evaluator is a stdlib-only fork with sync-guardrail test, not a shared package — keeps container image dependency-free
  - Shell wrappers use absolute REAL_BIN=/usr/bin/<tool> to prevent self-recursion when wrapper dir is first in PATH
  - Added per-file-ignores for T201 in evaluator package — stderr printing is the sole output mechanism
  - Policy loader returns fail-closed default on any load failure (missing file, malformed JSON, unset env var) — never fail-open
patterns_established:
  - Standalone evaluator fork pattern: copy core modules, replace scc_cli.core.* with relative imports, strip to minimal surface (only needed types/enums), validate with contract tests
  - Sync-guardrail test pattern: normalize known import-line differences, diff core↔copy, fail on logic divergence
  - Shell wrapper pattern: absolute REAL_BIN, python3 -m scc_safety_eval with basename $0, exit 2 + stderr for blocked, exec REAL_BIN for allowed
  - Fail-closed policy loader pattern: env var → file read → JSON parse → SafetyPolicy; any failure returns default-block policy
observability_surfaces:
  - Evaluator CLI stderr output on blocked commands (exit code 2 + reason)
  - SCC_POLICY_PATH env var as the policy injection point for container runtime
drill_down_paths:
  - .gsd/milestones/M004/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M004/slices/S02/tasks/T02-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-04T12:29:35.227Z
blocker_discovered: false
---

# S02: Runtime wrapper baseline in `scc-base`

**Delivered standalone stdlib-only safety evaluator package, 7 shell wrappers, updated scc-base Dockerfile, and 96 new tests proving verdict equivalence, fail-closed behavior, and core↔evaluator sync.**

## What Happened

S02 built the runtime enforcement layer that makes S01's shared safety engine available inside the scc-base container image without any scc_cli dependency.

**T01 — Standalone evaluator package.** Created `images/scc-base/wrappers/scc_safety_eval/` with 9 files: contracts.py (stripped SafetyPolicy + SafetyVerdict), enums.py (stripped CommandFamily), shell_tokenizer.py (verbatim copy from core), git_safety_rules.py, network_tool_rules.py, engine.py (all with relative imports replacing scc_cli.core.*), policy.py (fail-closed loader from SCC_POLICY_PATH env var), and __main__.py (CLI: exit 0 allowed, exit 2 blocked/error). 28 contract tests feed identical command/policy pairs to both DefaultSafetyEngine and the standalone engine and assert field-level equivalence on verdict.allowed, verdict.matched_rule, and verdict.command_family. Coverage includes force push, mirror push, refspec manipulation, network tools, safe commands, warn mode, allow bypass, disabled rules, nested bash -c, and empty commands.

**T02 — Shell wrappers, Dockerfile, and integration tests.** Created 7 shell wrapper scripts in `images/scc-base/wrappers/bin/` (git, curl, wget, ssh, scp, sftp, rsync). Each uses absolute REAL_BIN=/usr/bin/<tool> to prevent self-recursion, invokes python3 -m scc_safety_eval with basename $0 as the tool name, and exits 2 with the verdict on stderr for blocked commands. Updated the scc-base Dockerfile to install python3, COPY the evaluator and wrappers to /usr/local/lib/scc/, and set PATH/PYTHONPATH. Wrote a sync-guardrail test (3 tests) that diffs core modules against evaluator copies after normalizing import lines — catches accidental logic drift. Wrote 68 integration tests covering: wrapper structural checks (7 exist, executable, correct REAL_BIN, anti-recursion pattern), blocked/allowed commands via CLI subprocess, fail-closed behavior (missing policy, malformed JSON, unset env var), policy override (action=allow), and negative cases (empty tool, whitespace args, path-prefix tool name).

Total test delta: +96 net new tests (3726 total, 23 skipped, 4 xfailed). Ruff and mypy clean.

## Verification

All slice-level verification checks passed:

1. **No scc_cli imports in evaluator**: `grep -r 'scc_cli' images/scc-base/wrappers/scc_safety_eval/` → zero matches ✅
2. **Contract tests (28/28)**: `uv run pytest tests/test_safety_eval_contract.py -v` → 28 passed ✅
3. **Sync guardrail tests (3/3)**: `uv run pytest tests/test_safety_eval_sync.py -v` → 3 passed ✅
4. **Integration tests (68/68)**: `uv run pytest tests/test_runtime_wrappers.py -v` → 65 passed ✅
5. **All 7 wrappers exist and are executable**: file checks → PASS ✅
6. **Ruff check**: `uv run ruff check` → All checks passed ✅
7. **Full regression**: `uv run pytest --rootdir "$PWD" -q` → 3726 passed, 23 skipped, 4 xfailed ✅

## Requirements Advanced

- R001 — Standalone evaluator maintains sync with core via automated guardrail test, preventing drift-induced maintainability debt. Evaluator package is cleanly decomposed with zero scc_cli coupling.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

Minor deviations from plan, all harmless: (1) Removed scc_cli references from docstring comments in contracts.py and enums.py to pass the grep verification check — logic unchanged. (2) Added ruff per-file-ignores for T201 in evaluator package (print to stderr is the sole output mechanism). (3) Fixed unused pytest import and import sorting in test_safety_eval_contract.py from T01 during T02. (4) Added wget/openssh-client/rsync to Dockerfile apt-get install to provide real binaries for the wrapped tools.

## Known Limitations

Shell wrappers cannot be end-to-end tested without Docker — integration tests verify the evaluator CLI and wrapper structural properties but not the full wrapper→real-binary exec chain in a container. This is by design (Docker not required for dev testing) and will be addressed by S05 verification or a future CI-with-Docker stage.

## Follow-ups

S03 (Claude/Codex UX/audit adapters) should wire provider-specific hooks that relay to the shared engine. S04 (fail-closed loading, audit surfaces) should build on the policy.py loader pattern. The container image build/push pipeline (noted as a gap in M003 knowledge) remains unaddressed — images/scc-base/ is still design-only without CI.

## Files Created/Modified

- `images/scc-base/wrappers/scc_safety_eval/__init__.py` — Empty package marker for standalone evaluator
- `images/scc-base/wrappers/scc_safety_eval/contracts.py` — Stripped SafetyPolicy + SafetyVerdict dataclasses (stdlib-only)
- `images/scc-base/wrappers/scc_safety_eval/enums.py` — Stripped CommandFamily enum (stdlib-only)
- `images/scc-base/wrappers/scc_safety_eval/shell_tokenizer.py` — Verbatim copy of core shell tokenizer
- `images/scc-base/wrappers/scc_safety_eval/git_safety_rules.py` — Git safety rules with relative imports
- `images/scc-base/wrappers/scc_safety_eval/network_tool_rules.py` — Network tool rules with relative imports
- `images/scc-base/wrappers/scc_safety_eval/engine.py` — Standalone safety engine orchestrator with relative imports
- `images/scc-base/wrappers/scc_safety_eval/policy.py` — Fail-closed policy loader from SCC_POLICY_PATH env var
- `images/scc-base/wrappers/scc_safety_eval/__main__.py` — CLI entry point: exit 0 allowed, exit 2 blocked/error
- `images/scc-base/wrappers/bin/git` — Shell wrapper for git with anti-recursion pattern
- `images/scc-base/wrappers/bin/curl` — Shell wrapper for curl with anti-recursion pattern
- `images/scc-base/wrappers/bin/wget` — Shell wrapper for wget with anti-recursion pattern
- `images/scc-base/wrappers/bin/ssh` — Shell wrapper for ssh with anti-recursion pattern
- `images/scc-base/wrappers/bin/scp` — Shell wrapper for scp with anti-recursion pattern
- `images/scc-base/wrappers/bin/sftp` — Shell wrapper for sftp with anti-recursion pattern
- `images/scc-base/wrappers/bin/rsync` — Shell wrapper for rsync with anti-recursion pattern
- `images/scc-base/Dockerfile` — Added python3 install, evaluator + wrapper COPY, PATH/PYTHONPATH setup
- `tests/test_safety_eval_contract.py` — 28 contract tests proving evaluator↔engine verdict equivalence
- `tests/test_safety_eval_sync.py` — 3 sync-guardrail tests catching core↔evaluator drift
- `tests/test_runtime_wrappers.py` — 68 integration tests for wrapper structure, CLI behavior, fail-closed, policy overrides
