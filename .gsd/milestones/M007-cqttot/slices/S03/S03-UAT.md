# S03: Doctor provider-awareness and typed provider errors — UAT

**Milestone:** M007-cqttot
**Written:** 2026-04-05T13:31:07.878Z

## UAT: Doctor provider-awareness and typed provider errors

### Preconditions
- SCC installed from scc-sync-1.7.3 with `uv sync`
- Docker daemon running (for auth-check tests that need Docker)
- No specific provider configured (tests exercise both Claude and Codex paths)

### Test Cases

#### TC-1: Typed provider errors have actionable messages
```
Steps:
1. In Python: `from scc_cli.core.errors import ProviderNotReadyError; e = ProviderNotReadyError(provider_id='codex')`
2. Check e.user_message contains 'codex'
3. Check e.suggested_action contains 'scc doctor'
4. Check e.exit_code == 3

Expected: Error auto-populates message with provider name and actionable guidance.
```

#### TC-2: ProviderImageMissingError includes image reference
```
Steps:
1. `from scc_cli.core.errors import ProviderImageMissingError`
2. `e = ProviderImageMissingError(provider_id='codex', image_ref='scc-agent-codex:latest')`
3. Check e.user_message contains 'codex' and 'scc-agent-codex:latest'
4. Check e.suggested_action contains 'docker build'

Expected: Error message includes both provider and image reference for operator recovery.
```

#### TC-3: AuthReadiness dataclass is frozen and typed
```
Steps:
1. `from scc_cli.core.contracts import AuthReadiness`
2. `ar = AuthReadiness(status='present', mechanism='oauth_file', guidance='Auth is configured')`
3. Verify ar.status == 'present', ar.mechanism == 'oauth_file'
4. Attempt ar.status = 'missing' — should raise FrozenInstanceError

Expected: Immutable dataclass with correct field access.
```

#### TC-4: CheckResult has default category 'general'
```
Steps:
1. `from scc_cli.doctor.types import CheckResult`
2. `cr = CheckResult(name='Test', passed=True, message='ok')`
3. Verify cr.category == 'general'

Expected: Backward-compatible default category.
```

#### TC-5: check_provider_auth happy path (mocked Docker)
```
Steps:
1. Run `uv run pytest tests/test_doctor_provider_errors.py::TestCheckProviderAuth::test_happy_path_auth_present -v`

Expected: Test passes — check_provider_auth returns passed=True with category='provider' when Docker volume exists and auth file is found.
```

#### TC-6: check_provider_auth with missing volume
```
Steps:
1. Run `uv run pytest tests/test_doctor_provider_errors.py::TestCheckProviderAuth::test_volume_missing -v`

Expected: Test passes — check_provider_auth returns passed=False when Docker volume does not exist.
```

#### TC-7: check_provider_auth uses correct auth file per provider
```
Steps:
1. Run `uv run pytest tests/test_doctor_provider_errors.py::TestCheckProviderAuth::test_codex_auth_file -v`

Expected: Test passes — Codex uses auth.json, Claude uses .credentials.json.
```

#### TC-8: --provider flag validates against known providers
```
Steps:
1. Run `uv run pytest tests/test_doctor_provider_wiring.py::TestDoctorCmdProviderFlag::test_unknown_provider_exits_with_code_2 -v`

Expected: Unknown provider name causes exit code 2 with error message.
```

#### TC-9: --provider flag threads to run_doctor
```
Steps:
1. Run `uv run pytest tests/test_doctor_provider_wiring.py::TestDoctorCmdProviderFlag::test_valid_provider_passes_to_run_doctor -v`

Expected: Valid provider_id reaches run_doctor() and is forwarded to check functions.
```

#### TC-10: Category assignment classifies all check names correctly
```
Steps:
1. Run `uv run pytest tests/test_doctor_provider_wiring.py::TestCategoryAssignment -v`

Expected: All 10 tests pass — Git/Docker → backend, Provider Image/Auth → provider, Config/Safety → config, Worktree → worktree, unknown → general, pre-existing category preserved.
```

#### TC-11: Doctor JSON output includes category
```
Steps:
1. Run `uv run pytest tests/test_doctor_provider_wiring.py::TestJsonDataCategory -v`

Expected: JSON check dicts contain 'category' key with correct values.
```

#### TC-12: Doctor render groups by category with section headers
```
Steps:
1. Run `uv run pytest tests/test_doctor_provider_wiring.py::TestRenderGrouping -v`

Expected: Checks sorted by category order (backend→provider→config→worktree→general). Render does not crash with mixed categories.
```

#### TC-13: Full doctor test suite regression
```
Steps:
1. Run `uv run pytest tests/test_doctor_provider_wiring.py tests/test_doctor_provider_errors.py tests/test_doctor_image_check.py tests/test_doctor_checks.py -v`

Expected: All 101 tests pass with no regressions.
```

#### TC-14: Full project test suite
```
Steps:
1. Run `uv run pytest -q`

Expected: 4718+ tests pass, 0 failures. Mypy and ruff clean.
```
