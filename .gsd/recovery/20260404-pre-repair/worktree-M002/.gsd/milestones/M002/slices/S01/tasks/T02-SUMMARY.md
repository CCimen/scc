---
id: T02
parent: S01
milestone: M002
key_files:
  - tests/test_bootstrap.py
  - tests/test_core_contracts.py
key_decisions:
  - Applied ruff --fix to auto-correct unused import and unsorted import block rather than manually editing, ensuring idempotent lint compliance
duration: 
verification_result: passed
completed_at: 2026-04-03T17:50:25.304Z
blocker_discovered: false
---

# T02: Fix two ruff lint errors (F401 unused import, I001 unsorted imports) introduced by T01, restoring green lint+type+test baseline

**Fix two ruff lint errors (F401 unused import, I001 unsorted imports) introduced by T01, restoring green lint+type+test baseline**

## What Happened

The verification gate caught two ruff violations left by T01's import additions: an unused AgentProvider import in test_bootstrap.py (F401) and an unsorted import block in test_core_contracts.py (I001). Both are auto-fixable; ruff --fix resolved them in one pass. No logic or test semantics changed. All three verification commands now pass: ruff clean, mypy clean across 234 source files, full pytest suite at 3244 passed / 6 xfailed identical to T01 baseline.

## Verification

uv run ruff check → All checks passed. uv run mypy src/scc_cli → Success: no issues found in 234 source files. uv run pytest (task 4 files) → 10 passed, 3 xfailed. uv run pytest (full suite) → 3244 passed, 23 skipped, 6 xfailed, 1 xpassed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 2 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 3 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 4 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 5 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 6 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 7 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 8 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 9 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 10 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 11 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 12 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 13 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 14 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 15 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 16 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 17 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 18 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 19 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 20 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 21 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 22 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 23 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 24 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 25 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 26 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 27 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 28 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 29 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 30 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 31 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 32 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 33 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 34 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 35 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 36 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 37 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 38 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 39 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 40 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 41 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 42 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 43 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 44 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 45 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 46 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 47 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 48 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 49 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 50 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 51 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 52 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 53 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 54 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 55 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 56 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 57 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 58 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 59 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 60 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 61 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 62 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 63 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 64 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 65 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 66 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 67 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 68 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 69 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 70 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 71 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 72 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 73 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 74 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 75 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 76 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 77 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 78 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 79 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 80 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 81 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 82 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 83 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 84 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 85 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 86 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 87 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 88 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 89 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 90 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 91 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 92 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 93 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 94 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 95 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 96 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 97 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 98 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 99 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 100 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 101 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 102 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 103 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 104 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 105 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 106 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 107 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 108 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 109 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 110 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 111 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 112 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 113 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 114 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 115 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 116 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 117 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 118 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 119 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 120 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 121 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 122 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 123 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 124 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 125 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 126 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 127 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 128 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 129 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 130 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 131 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 132 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 133 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 134 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 135 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 136 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 137 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 138 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 139 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 140 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 141 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 142 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 143 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 144 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 145 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 146 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 147 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 148 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 149 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 150 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 151 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 152 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 153 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 154 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 155 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 156 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 157 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 158 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 159 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 160 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 161 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 162 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 163 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 164 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 165 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 166 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 167 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 168 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 169 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 170 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 171 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 172 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 173 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 174 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 175 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 176 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 177 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 178 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 179 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 180 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 181 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 182 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 183 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 184 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 185 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 186 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 187 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 188 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 189 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 190 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 191 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 192 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 193 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 194 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 195 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 196 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 197 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 198 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 199 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 200 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 201 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 202 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 203 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 204 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 205 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 206 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 207 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 208 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 209 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 210 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 211 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 212 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 213 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 214 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 215 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 216 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 217 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 218 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 219 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 220 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 221 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 222 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 223 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 224 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 225 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 226 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 227 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 228 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 229 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 230 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 231 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 232 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 233 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 234 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 235 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 236 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 237 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 238 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 239 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 240 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 241 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 242 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 243 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 244 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 245 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 246 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 247 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 248 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 249 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 250 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 251 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 252 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 253 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 254 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 255 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 256 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 257 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 258 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 259 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 260 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 261 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 262 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 263 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 264 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 265 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 266 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 267 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 268 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 269 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 270 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 271 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 272 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 273 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 274 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 275 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 276 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 277 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 278 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 279 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 280 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 281 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 282 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 283 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 284 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 285 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 286 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 287 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 288 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 289 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 290 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 291 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 292 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 293 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 294 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 295 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 296 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 297 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 298 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 299 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 300 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 301 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 302 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 303 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 304 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 305 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 306 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 307 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 308 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 309 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 310 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 311 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 312 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 313 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 314 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 315 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 316 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 317 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 318 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 319 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 320 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 321 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 322 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 323 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 324 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 325 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 326 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 327 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 328 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 329 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 330 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 331 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 332 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 333 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 334 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 335 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 336 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 337 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 338 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 339 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 340 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 341 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 342 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 343 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 344 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 345 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 346 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 347 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 348 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 349 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 350 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 351 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 352 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 353 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 354 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 355 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 356 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 357 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 358 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 359 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 360 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 361 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 362 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 363 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 364 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 365 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 366 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 367 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 368 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 369 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 370 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 371 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 372 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 373 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 374 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 375 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 376 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 377 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 378 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 379 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 380 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 381 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 382 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 383 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 384 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 385 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 386 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 387 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 388 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 389 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 390 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 391 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 392 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 393 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 394 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 395 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 396 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 397 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 398 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 399 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 400 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 401 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 402 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 403 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 404 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 405 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 406 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 407 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 408 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 409 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 410 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 411 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 412 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 413 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 414 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 415 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 416 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 417 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 418 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 419 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 420 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 421 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 422 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 423 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 424 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 425 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 426 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 427 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 428 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 429 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 430 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 431 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 432 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 433 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 434 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 435 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 436 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 437 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 438 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 439 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 440 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 441 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 442 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 443 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 444 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 445 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 446 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 447 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 448 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 449 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 450 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 451 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 452 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 453 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 454 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 455 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 456 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |
| 457 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 458 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4200ms |
| 459 | `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` | 0 | ✅ pass | 990ms |
| 460 | `uv run pytest -q` | 0 | ✅ pass | 35800ms |

## Deviations

Task plan described wiring AgentProvider.prepare_launch into the live path; the only outstanding gap at this verification cycle was two ruff lint errors from T01, fixed with ruff --fix.

## Known Issues

None.

## Files Created/Modified

- `tests/test_bootstrap.py`
- `tests/test_core_contracts.py`
