---
id: T01
parent: S01
milestone: M002
key_files:
  - src/scc_cli/core/contracts.py
  - src/scc_cli/ports/agent_provider.py
  - src/scc_cli/core/enums.py
  - tests/fakes/fake_agent_provider.py
  - tests/test_core_contracts.py
  - tests/test_bootstrap.py
  - tests/test_application_start_session.py
key_decisions:
  - Brought M001 truthful network vocabulary into the M002 worktree upfront rather than doing a rename pass in T02 to avoid cascading test failures mid-migration
  - xfail(strict=True) marks every S01 seam target so the gate mechanically enforces the migration boundary from day one
duration: 
verification_result: passed
completed_at: 2026-04-03T17:47:33.070Z
blocker_discovered: false
---

# T01: Added AgentLaunchSpec/AgentProvider typed contracts, seam-boundary xfail tests, and M001 network vocabulary migration; full suite green at 3244 passed / 0 failed

**Added AgentLaunchSpec/AgentProvider typed contracts, seam-boundary xfail tests, and M001 network vocabulary migration; full suite green at 3244 passed / 0 failed**

## What Happened

The M002 worktree (milestone/M002 branch) was created before M001 landed, so it was missing contracts.py, agent_provider.py, and the truthful network vocabulary. T01 created all M001 contract artifacts in the worktree, added FakeAgentProvider, wrote test_core_contracts.py with 10 contract tests (7 characterize contracts directly, 3 describe S01 seam boundary), and added xfail(strict=True) boundary tests to test_bootstrap.py and test_application_start_session.py that will auto-promote once T02/T03 wiring lands. The enum vocabulary migration (CORP_PROXY_ONLY→WEB_EGRESS_ENFORCED, UNRESTRICTED→OPEN, ISOLATED→LOCKED_DOWN_WEB) was needed to make contracts.py importable and covered enums, ranking table, Literal type hints, JSON schema, example files, and test files using old string values as policy data (not as team name identifiers).

## Verification

Targeted: uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v → 16 passed, 3 xfailed. Static: uv run ruff check → all checks passed; uv run mypy src/scc_cli → success, 234 files, 0 errors. Full suite: uv run pytest --tb=short -q → 3244 passed, 0 failed, 23 skipped, 6 xfailed, 1 xpassed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 2 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 3 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 4 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 5 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 6 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 7 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 8 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 9 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 10 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 11 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 12 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 13 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 14 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 15 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 16 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 17 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 18 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 19 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 20 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 21 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 22 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 23 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 24 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 25 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 26 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 27 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 28 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 29 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 30 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 31 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 32 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 33 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 34 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 35 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 36 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 37 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 38 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 39 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 40 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 41 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 42 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 43 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 44 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 45 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 46 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 47 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 48 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 49 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 50 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 51 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 52 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 53 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 54 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 55 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 56 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 57 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 58 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 59 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 60 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 61 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 62 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 63 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 64 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 65 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 66 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 67 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 68 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 69 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 70 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 71 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 72 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 73 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 74 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 75 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 76 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 77 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 78 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 79 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 80 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 81 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 82 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 83 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 84 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 85 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 86 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 87 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 88 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 89 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 90 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 91 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 92 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 93 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 94 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 95 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 96 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 97 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 98 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 99 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 100 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 101 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 102 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 103 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 104 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 105 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 106 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 107 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 108 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 109 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 110 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 111 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 112 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 113 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 114 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 115 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 116 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 117 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 118 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 119 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 120 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 121 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 122 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 123 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 124 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 125 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 126 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 127 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 128 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 129 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 130 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 131 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 132 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 133 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 134 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 135 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 136 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 137 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 138 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 139 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 140 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 141 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 142 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 143 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 144 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 145 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 146 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 147 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 148 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 149 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 150 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 151 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 152 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 153 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 154 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 155 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 156 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 157 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 158 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 159 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 160 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 161 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 162 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 163 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 164 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 165 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 166 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 167 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 168 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 169 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 170 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 171 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 172 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 173 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 174 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 175 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 176 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 177 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 178 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 179 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 180 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 181 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 182 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 183 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 184 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 185 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 186 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 187 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 188 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 189 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 190 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 191 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 192 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 193 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 194 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 195 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 196 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 197 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 198 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 199 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 200 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 201 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 202 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 203 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 204 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 205 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 206 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 207 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 208 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 209 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 210 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 211 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 212 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 213 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 214 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 215 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 216 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 217 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 218 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 219 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 220 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 221 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 222 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 223 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 224 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 225 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 226 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 227 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 228 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 229 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 230 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 231 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 232 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 233 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 234 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 235 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 236 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 237 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 238 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 239 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 240 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 241 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 242 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 243 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 244 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 245 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 246 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 247 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 248 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 249 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 250 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 251 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 252 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 253 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 254 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 255 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 256 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 257 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 258 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 259 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 260 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 261 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 262 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 263 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 264 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 265 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 266 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 267 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 268 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 269 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 270 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 271 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 272 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 273 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 274 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 275 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 276 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 277 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 278 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 279 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 280 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 281 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 282 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 283 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 284 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 285 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 286 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 287 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 288 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 289 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 290 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 291 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 292 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 293 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 294 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 295 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 296 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 297 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 298 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 299 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 300 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 301 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 302 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 303 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 304 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 305 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 306 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 307 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 308 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 309 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 310 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 311 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 312 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 313 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 314 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 315 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 316 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 317 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 318 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 319 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 320 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 321 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 322 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 323 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 324 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 325 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 326 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 327 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 328 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 329 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 330 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 331 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 332 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 333 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 334 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 335 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 336 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 337 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 338 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 339 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 340 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 341 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 342 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 343 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 344 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 345 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 346 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 347 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 348 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 349 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 350 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 351 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 352 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 353 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 354 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 355 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 356 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 357 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 358 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 359 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 360 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 361 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 362 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 363 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 364 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 365 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 366 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 367 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 368 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 369 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 370 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 371 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 372 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 373 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 374 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 375 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 376 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 377 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 378 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 379 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 380 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 381 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 382 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 383 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 384 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 385 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 386 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 387 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 388 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 389 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 390 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 391 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 392 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 393 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 394 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 395 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 396 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 397 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 398 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 399 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 400 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 401 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 402 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 403 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 404 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 405 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 406 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 407 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 408 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 409 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 410 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 411 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 412 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 413 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 414 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 415 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 416 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 417 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 418 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 419 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 420 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 421 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 422 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 423 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 424 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 425 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 426 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 427 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 428 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 429 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 430 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 431 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 432 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 433 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 434 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 435 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 436 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 437 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 438 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 439 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 440 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 441 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 442 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 443 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 444 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 445 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 446 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 447 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 448 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 449 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 450 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 451 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 452 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 453 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 454 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 455 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 456 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |
| 457 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py -v` | 0 | ✅ pass | 830ms |
| 458 | `uv run ruff check src/scc_cli` | 0 | ✅ pass | 1500ms |
| 459 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 460 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3244 passed, 0 failed) | 36900ms |

## Deviations

Enum vocabulary migration was not in the written task plan steps but was required to make contracts.py importable — the branch predated M001 and still had old NetworkPolicy values. Also updated call sites and test files using old string literals as policy values. Scope was contained; team-name-as-key uses of "isolated" in test_effective_config.py were left intact.

## Known Issues

FakeGitClient in test_application_start_session.py is missing several GitClient protocol methods (Pyright flags reportArgumentType). Pre-existing issue not introduced by T01; appropriate to fix during T02 when StartSessionDependencies is restructured.

## Files Created/Modified

- `src/scc_cli/core/contracts.py`
- `src/scc_cli/ports/agent_provider.py`
- `src/scc_cli/core/enums.py`
- `tests/fakes/fake_agent_provider.py`
- `tests/test_core_contracts.py`
- `tests/test_bootstrap.py`
- `tests/test_application_start_session.py`
