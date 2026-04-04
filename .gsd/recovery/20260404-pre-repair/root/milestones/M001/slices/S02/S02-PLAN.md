# S02: Truthful network vocabulary migration

**Goal:** Migrate SCC’s active terminology to open, web-egress-enforced, and locked-down-web without reintroducing fake security language or planned compatibility aliases.
**Demo:** After this: After this slice, active M001 code/docs/tests speak in truthful network terms instead of unrestricted/corp-proxy-only/isolated.

## Tasks
- [x] **T01: Mapped the legacy network-policy vocabulary by surface type and defined a safe migration order for S02.** — Search the repo for legacy network mode terms and classify each occurrence by surface: core contract, schema/config parsing, example fixture, test expectation, docs copy, or unrelated English prose. Use the inventory to define the smallest safe migration order.
  - Estimate: 30m
  - Files: .gsd/milestones/M001/slices/S02/tasks/T01-PLAN.md, src/scc_cli/**, tests/**, examples/**, README.md
  - Verify: rg -n "unrestricted|corp-proxy-only|isolated" . --glob '!**/.venv/**'
- [x] **T02: Migrated the live SCC network-policy surfaces to open, web-egress-enforced, and locked-down-web without touching unrelated prose uses.** — Update active M001 target surfaces from legacy network terms to the truthful vocabulary. Preserve actual behavior, remove planned compatibility aliases from core-target surfaces, and keep any non-network English uses of 'isolated' untouched when they do not name the network mode.
  - Estimate: 90m
  - Files: .gsd/milestones/M001/slices/S02/tasks/T02-PLAN.md, src/scc_cli/core/**, src/scc_cli/application/**, src/scc_cli/marketplace/**, src/scc_cli/schemas/**, tests/**, examples/**, README.md
  - Verify: rg -n "unrestricted|corp-proxy-only|isolated" src tests examples README.md && uv run ruff check && uv run mypy src/scc_cli
- [x] **T03: Validated the truthful network vocabulary migration by running the full fixed gate successfully on the renamed surfaces.** — Run focused and full verification after the rename work, then fix any mismatches introduced by the migration so the new terminology is stable and honest across code, docs, and tests.
  - Estimate: 45m
  - Files: .gsd/milestones/M001/slices/S02/tasks/T03-PLAN.md
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest
