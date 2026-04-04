---
estimated_steps: 14
estimated_files: 2
skills_used: []
---

# T01: Create provider destination registry with resolution and tests

Create `src/scc_cli/core/destination_registry.py` — a pure module mapping named destination set IDs (e.g. `"anthropic-core"`, `"openai-core"`) to typed `DestinationSet` objects with concrete provider hostnames. Expose `PROVIDER_DESTINATION_SETS` mapping and `resolve_destination_sets(names)` function. Also expose `destination_sets_to_allow_rules(sets)` helper that converts resolved `DestinationSet` tuples into allow-type `EgressRule` objects — this keeps rule generation reusable across backends.

Steps:
1. Create `src/scc_cli/core/destination_registry.py` with:
   - `PROVIDER_DESTINATION_SETS: dict[str, DestinationSet]` mapping `"anthropic-core"` → `DestinationSet(name="anthropic-core", destinations=("api.anthropic.com",), required=True, description="Anthropic API core access")`, and `"openai-core"` → similar for `api.openai.com`.
   - `resolve_destination_sets(names: tuple[str, ...]) -> tuple[DestinationSet, ...]` that looks up each name in the mapping, returning found sets. Raises `ValueError` for unknown names.
   - `destination_sets_to_allow_rules(sets: tuple[DestinationSet, ...]) -> tuple[EgressRule, ...]` that converts each destination in each set to an `EgressRule(target=host, allow=True, reason=f"provider-core: {set.name}")`.
2. Create `tests/test_destination_registry.py` with tests covering:
   - Known set resolution (anthropic-core, openai-core)
   - Unknown set raises ValueError
   - Empty input returns empty tuple
   - Allow-rule generation produces correct EgressRule objects
   - Rule targets match destination set hosts
   - Multiple sets produce combined rules
3. Verify: `uv run pytest --rootdir "$PWD" tests/test_destination_registry.py -q` passes, `uv run mypy src/scc_cli/core/destination_registry.py` clean.

## Inputs

- ``src/scc_cli/core/contracts.py` — DestinationSet and EgressRule dataclasses used by the registry`

## Expected Output

- ``src/scc_cli/core/destination_registry.py` — pure module with PROVIDER_DESTINATION_SETS mapping, resolve_destination_sets(), and destination_sets_to_allow_rules()`
- ``tests/test_destination_registry.py` — 8+ unit tests covering resolution, errors, and rule generation`

## Verification

uv run pytest --rootdir "$PWD" tests/test_destination_registry.py -q && uv run mypy src/scc_cli/core/destination_registry.py
