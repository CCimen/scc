---
id: T01
parent: S03
milestone: M002
key_files:
  - src/scc_cli/adapters/codex_agent_provider.py
  - tests/test_codex_agent_provider.py
key_decisions:
  - Codex argv is a single-element tuple ('codex',) with no extra flags, matching minimal Codex CLI invocation
  - supports_resume/supports_skills/supports_native_integrations all False for Codex
duration: 
verification_result: passed
completed_at: 2026-04-03T18:55:31.637Z
blocker_discovered: false
---

# T01: Add CodexAgentProvider adapter and 4 characterization tests pinning its AgentLaunchSpec and ProviderCapabilityProfile

**Add CodexAgentProvider adapter and 4 characterization tests pinning its AgentLaunchSpec and ProviderCapabilityProfile**

## What Happened

Created `src/scc_cli/adapters/codex_agent_provider.py` implementing the `AgentProvider` protocol with `provider_id='codex'`, `argv=('codex',)`, `required_destination_set='openai-core'`, and all boolean capability flags False. Created `tests/test_codex_agent_provider.py` with 4 characterization tests mirroring the Claude adapter tests: metadata assertions, clean-spec (no settings), settings-in-artifact-paths, and D003 env str-to-str contract guard. No existing files were modified.

## Verification

uv run pytest tests/test_codex_agent_provider.py -q → 4 passed; uv run ruff check → All checks passed; uv run mypy src/scc_cli → Success: no issues found in 236 source files

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 2 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 3 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 4 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 5 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 6 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 7 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 8 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 9 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 10 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 11 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 12 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 13 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 14 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 15 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 16 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 17 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 18 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 19 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 20 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 21 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 22 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 23 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 24 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 25 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 26 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 27 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 28 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 29 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 30 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 31 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 32 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 33 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 34 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 35 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 36 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 37 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 38 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 39 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 40 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 41 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 42 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 43 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 44 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 45 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 46 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 47 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 48 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 49 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 50 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 51 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 52 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 53 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 54 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 55 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 56 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 57 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 58 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 59 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 60 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 61 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 62 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 63 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 64 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 65 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 66 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 67 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 68 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 69 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 70 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 71 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 72 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 73 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 74 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 75 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 76 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 77 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 78 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 79 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 80 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 81 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 82 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 83 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 84 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 85 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 86 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 87 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 88 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 89 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 90 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 91 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 92 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 93 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 94 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 95 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 96 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 97 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 98 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 99 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 100 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 101 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 102 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 103 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 104 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 105 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 106 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 107 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 108 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 109 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 110 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 111 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 112 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 113 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 114 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 115 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 116 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 117 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 118 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 119 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 120 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 121 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 122 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 123 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 124 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 125 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 126 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 127 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 128 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 129 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 130 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 131 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 132 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 133 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 134 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 135 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 136 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 137 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 138 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 139 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 140 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 141 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 142 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 143 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 144 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 145 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 146 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 147 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 148 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 149 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 150 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 151 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 152 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 153 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 154 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 155 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 156 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 157 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 158 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 159 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 160 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 161 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 162 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 163 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 164 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 165 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 166 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 167 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 168 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 169 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 170 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 171 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 172 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 173 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 174 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 175 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 176 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 177 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 178 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 179 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 180 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 181 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 182 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 183 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 184 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 185 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 186 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 187 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 188 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 189 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 190 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 191 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 192 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 193 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 194 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 195 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 196 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 197 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 198 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 199 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 200 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 201 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 202 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 203 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 204 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 205 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 206 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 207 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 208 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 209 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 210 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 211 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 212 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 213 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 214 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 215 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 216 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 217 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 218 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 219 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 220 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 221 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 222 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 223 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 224 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 225 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 226 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 227 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 228 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 229 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 230 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 231 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 232 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 233 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 234 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 235 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 236 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 237 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 238 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 239 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 240 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 241 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 242 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 243 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 244 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 245 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 246 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 247 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 248 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 249 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 250 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 251 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 252 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 253 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 254 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 255 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 256 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 257 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 258 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 259 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 260 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 261 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 262 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 263 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 264 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 265 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 266 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 267 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 268 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 269 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 270 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 271 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 272 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 273 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 274 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 275 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 276 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 277 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 278 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 279 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 280 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 281 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 282 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 283 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 284 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 285 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 286 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 287 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 288 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 289 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 290 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 291 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 292 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 293 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 294 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 295 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 296 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 297 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 298 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 299 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 300 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 301 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 302 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 303 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 304 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 305 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 306 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 307 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 308 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 309 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 310 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 311 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 312 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 313 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 314 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 315 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 316 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 317 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 318 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 319 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 320 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 321 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 322 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 323 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 324 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 325 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 326 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 327 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 328 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 329 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 330 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 331 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 332 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 333 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 334 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 335 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 336 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 337 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 338 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 339 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 340 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 341 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 342 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |
| 343 | `uv run pytest tests/test_codex_agent_provider.py -q` | 0 | ✅ pass | 2200ms |
| 344 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 345 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3000ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/adapters/codex_agent_provider.py`
- `tests/test_codex_agent_provider.py`
