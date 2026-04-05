---
id: T10
parent: S05
milestone: M007-cqttot
key_files:
  - images/scc-base/Dockerfile
  - images/scc-agent-codex/Dockerfile
  - tests/test_image_structure.py
key_decisions:
  - (none)
duration: 
verification_result: passed
completed_at: 2026-04-05T15:44:34.953Z
blocker_discovered: false
---

# T10: scc-base now pre-creates both .claude and .codex dirs with 0700/uid1000; scc-agent-codex pins Codex CLI version via ARG; 25 structural tests cover all image Dockerfiles

**scc-base now pre-creates both .claude and .codex dirs with 0700/uid1000; scc-agent-codex pins Codex CLI version via ARG; 25 structural tests cover all image Dockerfiles**

## What Happened

Updated scc-base Dockerfile to create both /home/agent/.claude and /home/agent/.codex with chmod 0700 and chown agent:agent (previously only .claude existed). Updated scc-agent-codex Dockerfile to declare ARG CODEX_VERSION=latest for deterministic version pinning. Created tests/test_image_structure.py with 25 structural tests covering all four SCC image Dockerfiles without requiring Docker.

## Verification

uv run pytest tests/test_image_structure.py -v (25/25 passed), uv run ruff check (clean), uv run pytest tests/test_docs_truthfulness.py tests/test_provider_branding.py -v (41/41 passed), uv run pytest -q (4804 passed, 0 failed)

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_image_structure.py -v` | 0 | ✅ pass | 10700ms |
| 2 | `uv run ruff check` | 0 | ✅ pass | 5100ms |
| 3 | `uv run pytest tests/test_docs_truthfulness.py tests/test_provider_branding.py -v` | 0 | ✅ pass | 62800ms |
| 4 | `uv run pytest -q` | 0 | ✅ pass | 52700ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `images/scc-base/Dockerfile`
- `images/scc-agent-codex/Dockerfile`
- `tests/test_image_structure.py`
