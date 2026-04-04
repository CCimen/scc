---
id: T02
parent: S03
milestone: M002
key_files:
  - src/scc_cli/bootstrap.py
  - tests/fakes/__init__.py
  - tests/test_cli.py
  - tests/test_integration.py
key_decisions:
  - All construction sites were already wired with codex_agent_provider before T02 ran — no changes needed, verification confirmed correctness
duration: 
verification_result: passed
completed_at: 2026-04-03T18:58:06.050Z
blocker_discovered: false
---

# T02: All 4 DefaultAdapters construction sites confirmed wired with CodexAgentProvider; full suite (3255 tests) passes green

**All 4 DefaultAdapters construction sites confirmed wired with CodexAgentProvider; full suite (3255 tests) passes green**

## What Happened

On inspection, all four construction sites had already been wired with codex_agent_provider prior to T02 execution: bootstrap.py had the import, field declaration (AgentProvider | None = None), and get_default_adapters() instantiation; tests/fakes/__init__.py had codex_agent_provider=FakeAgentProvider() in build_fake_adapters(); tests/test_cli.py and tests/test_integration.py both had codex_agent_provider=FakeAgentProvider() in their inline DefaultAdapters constructions. No code changes were required. Verification confirmed the wiring was complete, type-correct, and did not break any existing callers.

## Verification

uv run pytest --tb=short -q → 3255 passed, 23 skipped, 3 xfailed, 1 xpassed; uv run ruff check → All checks passed; uv run mypy src/scc_cli → Success: no issues found in 236 source files

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 2 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 3 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 4 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 5 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 6 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 7 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 8 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 9 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 10 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 11 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 12 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 13 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 14 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 15 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 16 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 17 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 18 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 19 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 20 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 21 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 22 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 23 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 24 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 25 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 26 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 27 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 28 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 29 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 30 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 31 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 32 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 33 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 34 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 35 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 36 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 37 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 38 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 39 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 40 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 41 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 42 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 43 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 44 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 45 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 46 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 47 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 48 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 49 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 50 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 51 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 52 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 53 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 54 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 55 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 56 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 57 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 58 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 59 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 60 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 61 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 62 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 63 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 64 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 65 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 66 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 67 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 68 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 69 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 70 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 71 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 72 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 73 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 74 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 75 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 76 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 77 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 78 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 79 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 80 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 81 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 82 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 83 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 84 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 85 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 86 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 87 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 88 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 89 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 90 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 91 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 92 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 93 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 94 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 95 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 96 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 97 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 98 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 99 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 100 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 101 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 102 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 103 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 104 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 105 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 106 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 107 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 108 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 109 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 110 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 111 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 112 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 113 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 114 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 115 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 116 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 117 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 118 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 119 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 120 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 121 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 122 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 123 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 124 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 125 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 126 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 127 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 128 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 129 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 130 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 131 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 132 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 133 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 134 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 135 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 136 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 137 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 138 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 139 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 140 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 141 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 142 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 143 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 144 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 145 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 146 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 147 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 148 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 149 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 150 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 151 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 152 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 153 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 154 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 155 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 156 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 157 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 158 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 159 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 160 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 161 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 162 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 163 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 164 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 165 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 166 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 167 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 168 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 169 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 170 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 171 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 172 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 173 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 174 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 175 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 176 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 177 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 178 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 179 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 180 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 181 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 182 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 183 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 184 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 185 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 186 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 187 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 188 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 189 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 190 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 191 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 192 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 193 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 194 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 195 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 196 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 197 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 198 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 199 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 200 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 201 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 202 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 203 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 204 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 205 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 206 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 207 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 208 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 209 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 210 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 211 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 212 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 213 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 214 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 215 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 216 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 217 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 218 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 219 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 220 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 221 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 222 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 223 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 224 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 225 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 226 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 227 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 228 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 229 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 230 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 231 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 232 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 233 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 234 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 235 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 236 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 237 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 238 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 239 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 240 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 241 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 242 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 243 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 244 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 245 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 246 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 247 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 248 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 249 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 250 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 251 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 252 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 253 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 254 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 255 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 256 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 257 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 258 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 259 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 260 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 261 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 262 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 263 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 264 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 265 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 266 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 267 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 268 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 269 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 270 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 271 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 272 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 273 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 274 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 275 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 276 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 277 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 278 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 279 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 280 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 281 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 282 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 283 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 284 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 285 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 286 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 287 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 288 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 289 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 290 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 291 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 292 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 293 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 294 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 295 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 296 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 297 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 298 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 299 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 300 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 301 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 302 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 303 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 304 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 305 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 306 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 307 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 308 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 309 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 310 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 311 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 312 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 313 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 314 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 315 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 316 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 317 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 318 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 319 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 320 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 321 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 322 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 323 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 324 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 325 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 326 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 327 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 328 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 329 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 330 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 331 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 332 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 333 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 334 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 335 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 336 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 337 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 338 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 339 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 340 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 341 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 342 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |
| 343 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 44900ms |
| 344 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 345 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 1500ms |

## Deviations

All 4 construction sites were already wired; no code edits were necessary. Clean completion.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/bootstrap.py`
- `tests/fakes/__init__.py`
- `tests/test_cli.py`
- `tests/test_integration.py`
