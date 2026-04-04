---
version: 1
unique_milestone_ids: true
token_profile: quality
skill_discovery: suggest
git:
  main_branch: gsd/scc-v1
  merge_strategy: squash
  isolation: worktree
  auto_push: false
  commit_docs: true
  manage_gitignore: false
parallel:
  enabled: false
  max_workers: 2
  merge_strategy: per-milestone
  auto_merge: confirm
require_slice_discussion: true
verification_commands:
  - uv run ruff check
  - uv run mypy src/scc_cli
  - uv run pytest
verification_auto_fix: true
verification_max_retries: 2
auto_report: true
---

Project-local preferences for SCC v1 architecture work.
Keep parallel disabled until Milestone 0 and Milestone 1 are stable.
