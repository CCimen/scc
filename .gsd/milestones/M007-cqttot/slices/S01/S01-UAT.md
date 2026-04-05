# S01: ProviderRuntimeSpec model, fail-closed dispatch, and settings-path fix — UAT

**Milestone:** M007-cqttot
**Written:** 2026-04-05T12:40:15.899Z

## UAT: S01 — ProviderRuntimeSpec model, fail-closed dispatch, and settings-path fix

### Preconditions
- Working copy at scc-sync-1.7.3 with M007/S01 changes applied
- `uv sync` completed
- Python 3.10+

### Test Case 1: Registry returns correct Claude spec
**Steps:**
1. Run `uv run python -c "from scc_cli.core.provider_registry import get_runtime_spec; s = get_runtime_spec('claude'); print(s.display_name, s.config_dir, s.settings_path, s.data_volume)"`

**Expected:** Output shows `Claude Code .claude .claude/settings.json docker-claude-sandbox-data`

### Test Case 2: Registry returns correct Codex spec
**Steps:**
1. Run `uv run python -c "from scc_cli.core.provider_registry import get_runtime_spec; s = get_runtime_spec('codex'); print(s.display_name, s.config_dir, s.settings_path, s.data_volume)"`

**Expected:** Output shows `Codex .codex .codex/config.toml docker-codex-sandbox-data`

### Test Case 3: Unknown provider raises InvalidProviderError
**Steps:**
1. Run `uv run python -c "from scc_cli.core.provider_registry import get_runtime_spec; get_runtime_spec('gemini')"`

**Expected:** Raises `InvalidProviderError` with message containing `Unknown provider 'gemini'` and `Known providers: claude, codex`

### Test Case 4: Empty string provider raises InvalidProviderError
**Steps:**
1. Run `uv run python -c "from scc_cli.core.provider_registry import get_runtime_spec; get_runtime_spec('')"`

**Expected:** Raises `InvalidProviderError` with `provider_id=''`

### Test Case 5: ProviderRuntimeSpec is immutable
**Steps:**
1. Run `uv run python -c "from scc_cli.core.provider_registry import get_runtime_spec; s = get_runtime_spec('claude'); s.image_ref = 'hacked'"`

**Expected:** Raises `FrozenInstanceError` — fields cannot be reassigned

### Test Case 6: Settings path bug is fixed (Codex does not get Claude path)
**Steps:**
1. Run `uv run pytest tests/test_application_start_session.py -v -k "codex"` and inspect that any Codex-related settings path tests reference `.codex/config.toml`, not `.claude/settings.json`
2. Run `uv run python -c "from scc_cli.core.provider_registry import get_runtime_spec; assert get_runtime_spec('codex').settings_path != get_runtime_spec('claude').settings_path; print('PASS: different settings paths')"` 

**Expected:** PASS output; Claude and Codex have distinct settings paths

### Test Case 7: Fail-closed dispatch (dependencies.py)
**Steps:**
1. Run `uv run pytest tests/test_provider_dispatch.py -v -k "unknown"`

**Expected:** Tests assert `InvalidProviderError` is raised (not Claude fallback)

### Test Case 8: Doctor image check uses registry
**Steps:**
1. Run `uv run pytest tests/test_doctor_image_check.py -v`

**Expected:** All tests pass; doctor uses registry for image refs but falls back gracefully for unknown providers (diagnostic path)

### Test Case 9: Coexistence isolation via registry
**Steps:**
1. Run `uv run pytest tests/test_provider_coexistence.py -v`

**Expected:** All tests pass; Claude and Codex have different volumes, config dirs, and settings paths

### Test Case 10: Full regression suite
**Steps:**
1. Run `uv run pytest -q`

**Expected:** 4654 passed, 23 skipped, 2 xfailed — zero regressions

### Edge Cases
- **Registry key sync**: `test_registry_keys_match_known_providers` ensures PROVIDER_REGISTRY stays in sync with KNOWN_PROVIDERS from provider_resolution.py
- **Provider display names**: registry `display_name` values are non-empty and distinct per provider
- **Image refs**: registry `image_ref` values match the canonical constants from `core.image_contracts`
