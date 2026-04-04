---
id: T02
parent: S02
milestone: M001
key_files:
  - src/scc_cli/core/enums.py
  - src/scc_cli/core/network_policy.py
  - src/scc_cli/application/compute_effective_config.py
  - src/scc_cli/commands/config.py
  - src/scc_cli/commands/launch/sandbox.py
  - src/scc_cli/adapters/docker_sandbox_runtime.py
  - src/scc_cli/marketplace/schema.py
  - src/scc_cli/schemas/org-v1.schema.json
  - README.md
  - examples/11-release-readiness-org.json
  - tests/test_config_inheritance.py
  - tests/test_config_explain.py
key_decisions:
  - Rename both the enum values and enum member names so the core code reads in the new truthful vocabulary instead of carrying legacy symbol names.
  - Treat broad residual word hits as false positives unless they are part of network-policy values, enum names, diagnostics, or active examples/tests.
duration: 
verification_result: passed
completed_at: 2026-04-03T15:27:29.520Z
blocker_discovered: false
---

# T02: Migrated the live SCC network-policy surfaces to open, web-egress-enforced, and locked-down-web without touching unrelated prose uses.

**Migrated the live SCC network-policy surfaces to open, web-egress-enforced, and locked-down-web without touching unrelated prose uses.**

## What Happened

I migrated the active network-policy surfaces from the old vocabulary to the truthful names open, web-egress-enforced, and locked-down-web. The change covered the core enum and policy ordering helpers, config and runtime checks that branch on the policy, blocked-item diagnostics in effective-config computation, marketplace and JSON schema definitions, README examples, example org configs, and the affected tests. I also renamed the enum member symbols so the code no longer reads with legacy names behind new string values. After the edits, no legacy network-policy values or enum member names remained in the targeted code/test/example/doc surfaces, while unrelated English uses of the same words were left alone.

## Verification

Ran a targeted search proving that no legacy network-policy values or legacy enum member names remain in the active src/tests/examples/README/plan/constitution surfaces, then ran ruff and mypy successfully. LSP diagnostics on the edited Python modules were clean.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg -n 'network_policy[^\n]*(unrestricted|corp-proxy-only|isolated)|"network_policy":\s*"(unrestricted|corp-proxy-only|isolated)"|UNRESTRICTED|CORP_PROXY_ONLY|ISOLATED' src tests examples README.md PLAN.md CONSTITUTION.md --glob '!**/.venv/**'` | 1 | ✅ pass (no matches) | 27ms |
| 2 | `uv run ruff check` | 0 | ✅ pass | 41ms |
| 3 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 7802ms |

## Deviations

The verification search was narrowed to network-policy-bearing surfaces and old enum member names. A broad word search still hits unrelated prose such as allowed-plugin unrestricted semantics and isolated worktree language, which are intentionally out of scope for this rename.

## Known Issues

Historical and planning artifacts under .gsd still contain legacy vocabulary in prior task summaries and some current plan text. Broad text searches also still find unrelated uses of 'isolated' and 'unrestricted' in non-network contexts, which are intentionally unchanged.

## Files Created/Modified

- `src/scc_cli/core/enums.py`
- `src/scc_cli/core/network_policy.py`
- `src/scc_cli/application/compute_effective_config.py`
- `src/scc_cli/commands/config.py`
- `src/scc_cli/commands/launch/sandbox.py`
- `src/scc_cli/adapters/docker_sandbox_runtime.py`
- `src/scc_cli/marketplace/schema.py`
- `src/scc_cli/schemas/org-v1.schema.json`
- `README.md`
- `examples/11-release-readiness-org.json`
- `tests/test_config_inheritance.py`
- `tests/test_config_explain.py`
