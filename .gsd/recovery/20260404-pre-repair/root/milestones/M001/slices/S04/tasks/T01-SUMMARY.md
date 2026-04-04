---
id: T01
parent: S04
milestone: M001
key_files:
  - src/scc_cli/core/contracts.py
  - src/scc_cli/ports/agent_provider.py
  - src/scc_cli/core/__init__.py
  - tests/test_core_contracts.py
key_decisions:
  - Add the planned M001 contract types as frozen dataclasses in a dedicated core module instead of scattering them across existing ports and application code.
  - Introduce a new AgentProvider protocol alongside the existing AgentRunner port so the provider-neutral seam exists without destabilizing the current Claude-shaped flow.
duration: 
verification_result: passed
completed_at: 2026-04-03T15:39:21.948Z
blocker_discovered: false
---

# T01: Added the M001 typed contract layer and a new provider-neutral AgentProvider protocol with focused contract tests.

**Added the M001 typed contract layer and a new provider-neutral AgentProvider protocol with focused contract tests.**

## What Happened

I added the missing M001 typed contract layer in a new `src/scc_cli/core/contracts.py` module and introduced a provider-neutral `AgentProvider` protocol in `src/scc_cli/ports/agent_provider.py`. The contract module now defines RuntimeInfo, NetworkPolicyPlan, DestinationSet, EgressRule, SafetyPolicy, SafetyVerdict, AuditEvent, ProviderCapabilityProfile, and AgentLaunchSpec as frozen dataclasses where appropriate. I also exported the new contracts from `scc_cli.core` and added focused tests proving the truthful network-policy plan shape, runtime/safety immutability, audit-event structure, provider capability and launch-spec behavior, and the safety-policy rule map shape. This gives M001 the explicit typed seam it promised without forcing the whole application onto the new boundary prematurely.

## Verification

Checked the new contract module, provider protocol, and tests with LSP diagnostics, then ran the focused contract test suite. All diagnostics were clean and the tests passed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_core_contracts.py` | 0 | ✅ pass | 1170ms |

## Deviations

I introduced the M001 contracts as a thin standalone layer plus a new provider protocol, rather than migrating the existing launch flow to use them immediately. Full adoption is follow-on work for later milestones.

## Known Issues

The new contracts are present and tested, but the existing application flow still uses the older AgentRunner/SandboxSpec path. That is intentional for M001; adoption into the main launch boundary is later work.

## Files Created/Modified

- `src/scc_cli/core/contracts.py`
- `src/scc_cli/ports/agent_provider.py`
- `src/scc_cli/core/__init__.py`
- `tests/test_core_contracts.py`
