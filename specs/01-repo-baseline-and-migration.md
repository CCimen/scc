# Spec 01 — Repo Baseline And Migration

## Objective
Establish `scc-sync-1.7.3` as the only active implementation root and perform a one-time migration away from legacy naming and stale compatibility assumptions.

## Requirements
- Preserve the dirty `scc` tree as archive and rollback evidence.
- Do not continue active implementation in the archived tree.
- Migrate docs, configs, fixtures, and tests to the truthful network vocabulary in one pass.
- Remove long-term compatibility aliases from planned core surfaces after migration.
- Green baseline is required before further architecture work.

## Acceptance criteria
- Active work happens only in `scc-sync-1.7.3`.
- Old network names are absent from core contracts and new tests.
- Verification gate passes on the synced repo.
