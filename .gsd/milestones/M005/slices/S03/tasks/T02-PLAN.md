---
estimated_steps: 34
estimated_files: 3
skills_used: []
---

# T02: Extend NormalizedOrgConfig and normalizer for safety_net, stats, and from_dict helper

The current NormalizedOrgConfig silently drops `security.safety_net`, `stats`, and `config_source` fields (documented in KNOWLEDGE.md as a known gap). This task extends the config model and normalizer to cover these fields, and adds a `NormalizedOrgConfig.from_dict()` convenience class method that wraps `normalize_org_config()`. The from_dict helper is critical for T03-T05 because ~50+ test files construct inline `org_config = {...}` dicts — the helper avoids massive test fixture rewrites.

## Steps

1. Read `src/scc_cli/ports/config_models.py` and `src/scc_cli/adapters/config_normalizer.py` to understand existing patterns.
2. Add to `src/scc_cli/ports/config_models.py`:
   - `SafetyNetConfig` frozen dataclass: action (str, default 'block'), rules (dict[str, Any], default empty) — mirrors SafetyPolicy but lives in the config model layer
   - `StatsConfig` frozen dataclass: enabled (bool, default False), endpoint (str | None, default None)
   - Add `safety_net: SafetyNetConfig` field to `SecurityConfig` (default=SafetyNetConfig())
   - Add `stats: StatsConfig` field to `NormalizedOrgConfig` (default=StatsConfig())
   - Add `config_source: str | None` field to `NormalizedOrgConfig` (default=None)
   - Add `@classmethod from_dict(cls, raw: dict[str, Any]) -> NormalizedOrgConfig` that calls `normalize_org_config(raw)`
3. Update `src/scc_cli/adapters/config_normalizer.py`:
   - Add `_normalize_safety_net(raw: dict[str, Any] | None) -> SafetyNetConfig`
   - Add `_normalize_stats(raw: dict[str, Any] | None) -> StatsConfig`
   - Update `_normalize_security()` to include safety_net normalization
   - Update `normalize_org_config()` to pass stats and config_source
4. Extend `tests/test_config_normalization.py` with:
   - Tests for safety_net normalization (with action, with rules, missing, invalid)
   - Tests for stats normalization
   - Tests for config_source passthrough
   - Tests for NormalizedOrgConfig.from_dict() convenience method
5. Run full verification.

## Must-Haves

- [ ] SafetyNetConfig and StatsConfig exist as frozen dataclasses
- [ ] SecurityConfig.safety_net field added with safe default
- [ ] NormalizedOrgConfig.stats and .config_source fields added
- [ ] from_dict() class method works and returns NormalizedOrgConfig
- [ ] Normalizer covers security.safety_net extraction
- [ ] D016 respected: SafetyPolicy.rules stays dict[str, Any] — SafetyNetConfig.rules also uses dict[str, Any]
- [ ] All existing config normalization tests still pass

## Verification

- `uv run ruff check`
- `uv run mypy src/scc_cli`
- `uv run pytest tests/test_config_normalization.py -v`
- `uv run pytest --rootdir "$PWD" -q`

## Inputs

- ``src/scc_cli/ports/config_models.py` — existing config models to extend`
- ``src/scc_cli/adapters/config_normalizer.py` — existing normalizer to extend`
- ``src/scc_cli/core/contracts.py` — SafetyPolicy shape (D016: rules stays dict[str, Any])`
- ``tests/test_config_normalization.py` — existing tests to extend`

## Expected Output

- ``src/scc_cli/ports/config_models.py` — extended with SafetyNetConfig, StatsConfig, from_dict`
- ``src/scc_cli/adapters/config_normalizer.py` — extended normalizer covering safety_net and stats`
- ``tests/test_config_normalization.py` — extended with new field tests`

## Verification

uv run ruff check && uv run mypy src/scc_cli && uv run pytest tests/test_config_normalization.py -v && uv run pytest --rootdir "$PWD" -q
