# M002: M002: Provider-Neutral Launch Adoption

## Vision
M002: Provider-Neutral Launch Adoption

## Slice Overview
| ID | Slice | Risk | Depends | Done | After this |
|----|-------|------|---------|------|------------|
| S01 | Live launch-path adoption of AgentProvider and AgentLaunchSpec | high | — | ✅ | TBD |
| S02 | Claude adapter extraction and cleanup | high | S01 | ✅ | TBD |
| S03 | Codex adapter as a first-class provider on the same seam | high | S01 | ✅ | TBD |
| S04 | Pre-launch validation and durable audit sink | medium | S01, S02, S03 | ⬜ | TBD |
| S05 | Hardening, diagnostics, and decomposition follow-through | medium | S02, S03, S04 | ⬜ | TBD |
| S06 | Restore milestone-exit contract gate | medium | S05 | ✅ | After this slice, `uv run ruff check`, `uv run mypy src/scc_cli`, and `uv run pytest --rootdir "$PWD" -q` all pass again in the active worktree, so M002 can be revalidated and sealed. |
