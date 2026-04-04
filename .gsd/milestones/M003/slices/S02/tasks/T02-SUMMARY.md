---
id: T02
parent: S02
milestone: M003
key_files:
  - src/scc_cli/core/image_contracts.py
  - images/scc-base/Dockerfile
  - images/scc-agent-claude/Dockerfile
  - tests/test_image_contracts.py
key_decisions:
  - ImageRef field order puts repository first (required) before optional registry
  - image_ref parser uses dot/colon/localhost heuristic for registry detection
  - Dockerfiles use ubuntu:22.04 base and NodeSource for Node.js 20 LTS
duration: 
verification_result: passed
completed_at: 2026-04-04T09:06:37.696Z
blocker_discovered: false
---

# T02: Added frozen ImageRef dataclass with full_ref()/image_ref() roundtrip, SCC image constants, and Dockerfiles for scc-base and scc-agent-claude

**Added frozen ImageRef dataclass with full_ref()/image_ref() roundtrip, SCC image constants, and Dockerfiles for scc-base and scc-agent-claude**

## What Happened

Created src/scc_cli/core/image_contracts.py with a frozen ImageRef dataclass holding repository, registry, tag, and digest fields. The full_ref() method serializes to canonical Docker reference format, and image_ref() parses raw reference strings back. Defined SCC_BASE_IMAGE, SCC_CLAUDE_IMAGE, and SCC_CLAUDE_IMAGE_REF constants. Created Dockerfiles for scc-base (Ubuntu 22.04 + agent user + CLI tools) and scc-agent-claude (Node.js 20 + Claude CLI). Wrote 23 unit tests covering serialization, parsing, immutability, and constants.

## Verification

All verification passed: pytest 23/23 targeted tests, mypy clean on module and full codebase (245 files), ruff check clean, full suite 3310 passed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_image_contracts.py -q` | 0 | ✅ pass | 1100ms |
| 2 | `uv run mypy src/scc_cli/core/image_contracts.py` | 0 | ✅ pass | 4400ms |
| 3 | `uv run ruff check` | 0 | ✅ pass | 58000ms |
| 4 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 58000ms |
| 5 | `uv run pytest -q` | 0 | ✅ pass | 52740ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/core/image_contracts.py`
- `images/scc-base/Dockerfile`
- `images/scc-agent-claude/Dockerfile`
- `tests/test_image_contracts.py`
