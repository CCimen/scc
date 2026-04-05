# S01 Research — ProviderRuntimeSpec model, fail-closed dispatch, and settings-path fix

## Summary

This is targeted research. The patterns are established (frozen dataclass registry, fail-closed lookup, typed errors). The decisions (D029–D034, D041) are precise. The work is consolidating 5 scattered dicts into one typed registry, adding a new error type, wiring the registry into existing consumers, and fixing the hardcoded Claude settings path.

## Recommendation

Three tasks, ordered by dependency:

1. **ProviderRuntimeSpec model + registry module + InvalidProviderError** — Create the type in `core/contracts.py`, the registry in `src/scc_cli/provider_registry.py`, the error in `core/errors.py`. Test the registry and error exhaustively. This unblocks everything.
2. **Wire registry into dispatch and start_session, fix settings-path** — Replace the 5 scattered dicts in `start_session.py` and `dependencies.py` with registry lookups. Fix the hardcoded settings path at `start_session.py:286`. Make `_build_sandbox_spec` fail-closed on unknown providers. Update `provider_resolution.py:get_provider_display_name` to delegate to the registry.
3. **Update tests, fix fallback assertions, update coexistence/dispatch tests** — Flip `test_unknown_provider_falls_back_to_claude` (and its runner twin at line 62) to assert `InvalidProviderError`. Update coexistence tests to import from registry instead of scattered dicts. Add OCI runtime missing-spec-field tests.

## Implementation Landscape

### Files to create
| File | Purpose |
|------|---------|
| `src/scc_cli/provider_registry.py` | `PROVIDER_REGISTRY` dict, `get_runtime_spec()` fail-closed lookup, re-export of `ProviderRuntimeSpec`. Composition-layer module alongside `bootstrap.py` (D034). |

### Files to modify
| File | What changes | Lines |
|------|--------------|-------|
| `src/scc_cli/core/contracts.py` (~240 lines) | Add `ProviderRuntimeSpec` frozen dataclass: `provider_id`, `display_name`, `image_ref`, `config_dir`, `settings_path`, `data_volume` | +15 |
| `src/scc_cli/core/errors.py` (~534 lines) | Add `InvalidProviderError(SCCError)` with `provider_id`, `known_providers`, user-facing message | +20 |
| `src/scc_cli/application/start_session.py` (~477 lines) | Remove `_PROVIDER_IMAGE_REF`, `_PROVIDER_DATA_VOLUME`, `_PROVIDER_CONFIG_DIR` dicts. Import from `provider_registry`. Replace `.get(..., claude_fallback)` with `get_runtime_spec()` (which raises on unknown). Fix hardcoded `AGENT_CONFIG_DIR / "settings.json"` at line 286 to use `spec.settings_path` from registry. | ~-20, +10 |
| `src/scc_cli/commands/launch/dependencies.py` (~130 lines) | Replace `_PROVIDER_DISPATCH.get(provider_id, _PROVIDER_DISPATCH[_DEFAULT_PROVIDER_ID])` with fail-closed lookup. Import `InvalidProviderError`. | ~5 |
| `src/scc_cli/core/provider_resolution.py` (~75 lines) | `get_provider_display_name()` can optionally delegate to registry or stay as-is (it already title-cases unknowns gracefully — not a launch path). Decision: keep it independent for now since it's used in display contexts where graceful degradation is correct. | 0 |

### Files to update tests in
| File | What changes |
|------|--------------|
| `tests/test_provider_dispatch.py` | `test_unknown_provider_falls_back_to_claude` → assert `InvalidProviderError`. Same for `test_unknown_provider_falls_back_to_claude_runner`. |
| `tests/test_provider_coexistence.py` | Change imports from `start_session._PROVIDER_*` to `provider_registry`. Tests themselves mostly stay the same — they test identity isolation. |
| `tests/test_application_start_session.py` | Verify `_build_sandbox_spec` uses registry. Test that unknown provider raises instead of falling back. |
| New: `tests/test_provider_registry.py` | Registry lookup tests: known providers return correct spec, unknown raises `InvalidProviderError`, registry entries have non-empty fields, registry covers all KNOWN_PROVIDERS. |

### The settings-path bug (the "fix" part of the slice title)
Line 286 of `start_session.py`:
```python
settings_path = Path("/home/agent") / AGENT_CONFIG_DIR / "settings.json"
```
This hardcodes Claude's `.claude/settings.json` for ALL providers. For Codex, it should be `.codex/config.toml`. The fix: use `ProviderRuntimeSpec.settings_path` from the registry, resolved from the provider_id that's already available in `_build_agent_settings()` context.

The caller `_build_agent_settings` receives `agent_runner` but not `provider_id`. The fix requires threading `provider_id` (or the spec) into this function. The cleanest path: pass the `ProviderRuntimeSpec` obtained from the registry (already looked up in `_build_sandbox_spec`) into `_build_agent_settings`, and use `spec.settings_path` to construct the container path.

### OCI runtime impact
`_inject_settings` in `oci_sandbox_runtime.py` currently calls `json.dumps(spec.agent_settings.content)` — this is a Claude-specific serialization assumption. However, fixing this is S02 scope (D035 — `AgentSettings.rendered_bytes`). S01 only needs to ensure the *path* is correct, not the serialization format. The path is already carried on `AgentSettings.path`, so once S01 fixes the path construction, S02 can fix the serialization independently.

### Fail-closed boundary (D032)
Three sites currently fall back to Claude for unknown providers:
1. `dependencies.py:build_start_session_dependencies()` line: `_PROVIDER_DISPATCH.get(provider_id, _PROVIDER_DISPATCH[_DEFAULT_PROVIDER_ID])` → must raise `InvalidProviderError`
2. `start_session.py:_build_sandbox_spec()` lines 320-322: `.get(resolved_pid, SCC_CLAUDE_IMAGE_REF)` → must raise via registry lookup
3. `provider_resolution.py:resolve_active_provider()` already raises `ValueError` for unknown providers → keep this, but downstream consumers that catch the resolved ID should never silently substitute

Legacy/migration boundaries (D032 allows Claude default here):
- `SessionRecord.provider_id=None` → `"claude"` during deserialization — this is display/history, not active launch. No change needed in S01.

### Constraints
- `provider_registry.py` must NOT import from adapters or commands — it's composition-layer infrastructure
- `ProviderRuntimeSpec` in `core/contracts.py` must NOT carry provider-specific launch argv (D029 says runner-owned)
- `get_provider_display_name` in `provider_resolution.py` stays independent — it serves display contexts where graceful title-casing of unknowns is correct behavior (branding, doctor rendering)
- The `KNOWN_PROVIDERS` tuple in `provider_resolution.py` should stay in sync with the registry keys — consider a guardrail test

### Verification
```bash
# Unit tests
uv run pytest tests/test_provider_registry.py tests/test_provider_dispatch.py tests/test_provider_coexistence.py tests/test_provider_resolution.py tests/test_application_start_session.py -v

# Type checking
uv run mypy src/scc_cli/provider_registry.py src/scc_cli/core/contracts.py src/scc_cli/core/errors.py src/scc_cli/application/start_session.py src/scc_cli/commands/launch/dependencies.py

# Lint
uv run ruff check src/scc_cli/provider_registry.py

# Full suite (regression)
uv run pytest -q
```

### Doctor module note
`src/scc_cli/doctor/checks/environment.py` has its own `image_map` dict (`{"claude": SCC_CLAUDE_IMAGE_REF, "codex": SCC_CODEX_IMAGE_REF}`) with a Claude fallback. This is a downstream consumer that S01 should update to use the registry — it's a natural fit and eliminates one more scattered dict. However, if scoping is tight, it can wait for S04 (legacy cleanup). Recommend including it in S01 since it's a 3-line change.

### Risk assessment
Low-medium. The registry is a new module but the pattern (frozen dataclass + dict lookup + typed error) is thoroughly established in the codebase. The settings-path fix requires threading a value through `_build_agent_settings` which touches a moderately complex function, but the change is mechanical. The fail-closed behavior change will break exactly 2 existing tests that assert fallback — both need to be flipped to assert the new error.

### Skills
No external skills needed. This is pure Python dataclass/registry work using existing codebase patterns.
