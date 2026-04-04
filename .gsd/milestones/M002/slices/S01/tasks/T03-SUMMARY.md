---
id: T03
parent: S01
milestone: M002
key_files:
  - src/scc_cli/adapters/claude_agent_provider.py
  - src/scc_cli/bootstrap.py
  - src/scc_cli/application/start_session.py
  - tests/fakes/__init__.py
  - tests/test_bootstrap.py
  - tests/test_application_start_session.py
  - tests/test_cli.py
  - tests/test_integration.py
key_decisions:
  - ClaudeAgentProvider.prepare_launch produces a clean AgentLaunchSpec with no nested dicts in env; settings content is carried in artifact_paths, not injected as env vars
  - agent_provider on StartSessionDependencies defaults to None for backward compatibility
  - _build_agent_launch_spec returns None in dry_run mode, mirroring the sandbox_spec behavior
  - Fixed tests/fakes/__init__.py:build_fake_adapters() and two inline DefaultAdapters() constructions to include agent_provider
duration: 
verification_result: passed
completed_at: 2026-04-03T18:00:47.225Z
blocker_discovered: false
---

# T03: Wired ClaudeAgentProvider into DefaultAdapters and launch path, promoting all 3 S01 xfail seam tests to passing; full suite at 3247 passed / 0 failed

**Wired ClaudeAgentProvider into DefaultAdapters and launch path, promoting all 3 S01 xfail seam tests to passing; full suite at 3247 passed / 0 failed**

## What Happened

T03 completed the S01 migration by wiring the typed provider seam end-to-end. Created ClaudeAgentProvider adapter implementing the AgentProvider protocol. Added agent_provider field to DefaultAdapters and wired ClaudeAgentProvider() in get_default_adapters(). Added agent_provider (optional, None default) to StartSessionDependencies, agent_launch_spec to StartSessionPlan, and _build_agent_launch_spec helper into prepare_start_session. Updated tests/fakes/__init__.py:build_fake_adapters() and two inline DefaultAdapters constructions in test_cli.py and test_integration.py. Removed xfail decorators from the 3 S01 seam-boundary tests and cleaned up stale type: ignore annotations and unused pytest imports.

## Verification

All 3 slice verification commands passed: ruff check clean, mypy success on 235 source files, pytest 3247 passed / 0 failed / 23 skipped. The 3 seam-boundary tests that were xfail since T01 now pass as regular tests.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 2 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 3 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 4 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 5 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 6 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 7 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 8 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 9 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 10 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 11 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 12 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 13 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 14 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 15 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 16 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 17 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 18 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 19 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 20 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 21 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 22 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 23 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 24 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 25 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 26 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 27 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 28 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 29 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 30 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 31 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 32 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 33 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 34 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 35 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 36 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 37 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 38 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 39 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 40 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 41 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 42 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 43 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 44 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 45 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 46 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 47 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 48 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 49 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 50 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 51 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 52 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 53 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 54 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 55 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 56 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 57 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 58 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 59 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 60 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 61 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 62 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 63 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 64 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 65 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 66 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 67 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 68 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 69 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 70 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 71 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 72 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 73 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 74 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 75 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 76 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 77 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 78 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 79 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 80 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 81 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 82 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 83 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 84 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 85 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 86 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 87 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 88 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 89 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 90 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 91 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 92 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 93 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 94 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 95 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 96 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 97 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 98 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 99 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 100 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 101 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 102 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 103 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 104 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 105 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 106 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 107 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 108 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 109 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 110 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 111 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 112 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 113 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 114 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 115 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 116 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 117 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 118 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 119 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 120 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 121 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 122 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 123 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 124 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 125 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 126 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 127 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 128 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 129 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 130 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 131 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 132 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 133 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 134 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 135 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 136 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 137 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 138 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 139 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 140 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 141 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 142 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 143 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 144 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 145 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 146 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 147 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 148 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 149 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 150 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 151 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 152 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 153 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 154 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 155 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 156 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 157 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 158 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 159 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 160 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 161 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 162 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 163 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 164 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 165 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 166 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 167 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 168 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 169 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 170 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 171 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 172 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 173 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 174 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 175 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 176 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 177 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 178 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 179 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 180 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 181 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 182 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 183 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 184 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 185 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 186 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 187 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 188 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 189 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 190 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 191 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 192 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 193 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 194 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 195 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 196 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 197 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 198 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 199 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 200 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 201 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 202 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 203 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 204 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 205 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 206 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 207 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 208 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 209 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 210 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 211 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 212 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 213 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 214 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 215 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 216 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 217 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 218 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 219 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 220 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 221 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 222 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 223 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 224 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 225 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 226 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 227 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 228 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 229 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 230 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 231 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 232 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 233 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 234 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 235 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 236 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 237 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 238 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 239 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 240 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 241 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 242 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 243 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 244 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 245 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 246 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 247 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 248 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 249 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 250 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 251 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 252 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 253 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 254 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 255 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 256 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 257 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 258 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 259 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 260 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 261 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 262 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 263 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 264 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 265 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 266 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 267 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 268 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 269 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 270 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 271 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 272 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 273 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 274 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 275 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 276 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 277 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 278 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 279 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 280 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 281 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 282 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 283 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 284 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 285 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 286 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 287 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 288 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 289 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 290 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 291 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 292 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 293 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 294 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 295 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 296 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 297 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 298 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 299 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 300 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 301 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 302 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 303 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 304 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 305 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 306 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 307 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 308 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 309 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 310 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 311 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 312 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 313 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 314 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 315 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 316 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 317 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 318 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 319 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 320 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 321 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 322 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 323 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 324 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 325 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 326 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 327 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 328 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 329 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 330 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 331 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 332 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 333 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 334 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 335 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 336 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 337 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 338 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 339 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 340 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 341 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 342 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |
| 343 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 344 | `uv run mypy src/scc_cli` | 0 | ✅ pass (235 files) | 7500ms |
| 345 | `uv run pytest --tb=short -q` | 0 | ✅ pass (3247 passed, 0 failed) | 39700ms |

## Deviations

Two inline DefaultAdapters() constructions in test_cli.py and test_integration.py (not covered by build_fake_adapters) required updating to add agent_provider — not in the written task plan steps but straightforward call-site fixes.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/adapters/claude_agent_provider.py`
- `src/scc_cli/bootstrap.py`
- `src/scc_cli/application/start_session.py`
- `tests/fakes/__init__.py`
- `tests/test_bootstrap.py`
- `tests/test_application_start_session.py`
- `tests/test_cli.py`
- `tests/test_integration.py`
