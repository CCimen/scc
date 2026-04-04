# S06: Diagnostics, docs truthfulness, guardrails, and milestone validation for team-pack model

**Goal:** Verify diagnostics/docs truthfulness for the team-pack model and rendered native surfaces. Re-enable file-size/complexity guardrails. Remove transitional ruff ignores. Ensure all operator-facing surfaces (doctor, support-bundle, docs, error messages) accurately describe the governed-artifact/team-pack model, and do not claim capabilities (e.g. Codex parity) that are not yet implemented. Final milestone validation.
**Demo:** After this: Diagnostics show active team context, effective bundles, shared vs native, rendered/skipped/blocked; docs claims match implementation; file-size/complexity guardrails pass without xfail; milestone validation passes

## Tasks
- [x] **T01: Added three doctor checks (team context, bundle resolution, catalog health) and governed-artifact diagnostics to support bundle** — Extend doctor checks to report:
1. Active team context and enabled bundles
2. Selected provider and effective render plan
3. Rendered vs skipped vs blocked artifacts with reasons
4. Bundle resolution health (all referenced bundles exist, all artifacts resolvable)

Extend support bundle to include:
1. Effective ArtifactRenderPlan for the active session
2. Renderer results: which files written, which skipped, which failed
3. Bundle catalog summary from org config

Add tests for both diagnostic surfaces.
  - Estimate: 2h
  - Files: src/scc_cli/doctor/checks/artifacts.py, src/scc_cli/application/support_bundle.py, tests/test_doctor_artifact_checks.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest tests/test_doctor_artifact_checks.py -v && uv run pytest --rootdir "$PWD" -q
- [x] **T02: Fixed four truthfulness gaps: Codex capability_profile, portable-artifact contract mismatch, renderer overclaiming, and transitional marketplace sync; added governed_artifacts/enabled_bundles to schema; removed stale xfail; fixed import boundary violation** — Review and update all docs, README, examples, schemas, and error messages to:
1. Accurately describe the governed-artifact/team-pack model
2. Not claim Codex bundle parity beyond what codex_renderer implements
3. Use consistent language: 'team pack' / 'bundle' for the team-facing unit, 'governed artifact' for the policy unit
4. Show that provider surfaces are asymmetric and that's intentional
5. Update org-v1.schema.json to include governed_artifacts and enabled_bundles sections
6. Add truthfulness guardrail tests for team-pack language

This is a truthfulness pass — add only language that matches real implementation, remove or qualify claims that exceed it.
  - Estimate: 1h30m
  - Files: README.md, src/scc_cli/schemas/org-v1.schema.json, tests/test_docs_truthfulness.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest tests/test_docs_truthfulness.py -v && uv run pytest --rootdir "$PWD" -q
- [x] **T03: Removed xfail from function-size guardrail, extracted 4 oversized functions below 300-line limit, confirmed all ruff ignores are permanent** — 1. Review tests/test_file_sizes.py and tests/test_function_sizes.py — remove all xfail markers, fix any remaining violations
2. Review pyproject.toml [tool.ruff.lint.per-file-ignores] — remove transitional ignores, document permanent ones
3. Re-run guardrails to confirm they pass
4. Update any modules still above 800 lines if any remain from S02 decomposition drift
5. Verify no new modules exceed the guardrail thresholds
  - Estimate: 1h30m
  - Files: pyproject.toml, tests/test_file_sizes.py, tests/test_function_sizes.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest tests/test_file_sizes.py tests/test_function_sizes.py -v && uv run pytest --rootdir "$PWD" -q
- [x] **T04: Ran full M005 verification gate and validated all exit criteria; wrote VALIDATION.md with evidence for each criterion** — 1. Run the full M005 verification gate: ruff check + mypy + pyright + pytest --cov --cov-branch
2. Verify all M005 exit criteria from M005-CONTEXT.md:
   - All modules over 1100 lines reduced below threshold
   - All modules over 800 lines split or justified
   - Direct runtime/backend imports from core/app/commands/UI removed
   - Internal config/policy logic uses typed models
   - Silent failure swallowing removed from maintained paths
   - File/function size tests pass without xfail
   - Docs and diagnostics are truthful
3. Write VALIDATION.md with evidence for each criterion
4. Complete the milestone
  - Estimate: 1h
  - Files: .gsd/milestones/M005/VALIDATION.md
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest --rootdir "$PWD" -q
