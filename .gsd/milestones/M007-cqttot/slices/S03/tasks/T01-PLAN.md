---
estimated_steps: 6
estimated_files: 6
skills_used: []
---

# T01: Add typed provider errors, AuthReadiness model, category field, and check_provider_auth

Pure additive task — add all new types and one new check function. No changes to existing control flow.

1. Add ProviderNotReadyError(PrerequisiteError) and ProviderImageMissingError(PrerequisiteError) to core/errors.py. Both carry provider_id field and auto-populate user_message/suggested_action in __post_init__. ProviderNotReadyError is the general readiness error (exit_code=3). ProviderImageMissingError is the specific image-not-found case (exit_code=3). Follow InvalidProviderError pattern.

2. Add AuthReadiness frozen dataclass to core/contracts.py with fields: status (str — 'missing' or 'present'), mechanism (str — 'oauth_file' or 'auth_json_file'), guidance (str — actionable next step).

3. Add `category: str = 'general'` field to CheckResult in doctor/types.py. Default ensures backward compatibility.

4. Add check_provider_auth(provider_id: str | None = None) to doctor/checks/environment.py. Logic: resolve provider via get_runtime_spec(), determine auth file name (.credentials.json for claude, auth.json for codex), run `docker volume inspect <volume>` then `docker run --rm -v <volume>:/check alpine test -f /check/<auth_file>` via subprocess.run (mocked in tests). Return CheckResult with passed=True/False and category='provider'. Export from doctor/checks/__init__.py.

5. Write tests in tests/test_doctor_provider_errors.py: ProviderNotReadyError message/action/exit_code, ProviderImageMissingError message/action/exit_code, AuthReadiness field access, check_provider_auth happy path, check_provider_auth missing auth, check_provider_auth volume missing, check_provider_auth subprocess timeout, check_provider_auth unknown provider fallback, CheckResult category default.

## Inputs

- ``src/scc_cli/core/errors.py` — existing error hierarchy, follow InvalidProviderError pattern`
- ``src/scc_cli/core/contracts.py` — add AuthReadiness alongside ProviderRuntimeSpec`
- ``src/scc_cli/doctor/types.py` — add category field to CheckResult`
- ``src/scc_cli/doctor/checks/environment.py` — add check_provider_auth() alongside check_provider_image()`
- ``src/scc_cli/core/provider_registry.py` — import get_runtime_spec() for auth check`

## Expected Output

- ``src/scc_cli/core/errors.py` — ProviderNotReadyError, ProviderImageMissingError added`
- ``src/scc_cli/core/contracts.py` — AuthReadiness frozen dataclass added`
- ``src/scc_cli/doctor/types.py` — category field added to CheckResult`
- ``src/scc_cli/doctor/checks/environment.py` — check_provider_auth() function added`
- ``src/scc_cli/doctor/checks/__init__.py` — check_provider_auth exported`
- ``tests/test_doctor_provider_errors.py` — test file with ~12 tests covering new types and check function`

## Verification

uv run pytest tests/test_doctor_provider_errors.py -v && uv run mypy src/scc_cli/core/errors.py src/scc_cli/core/contracts.py src/scc_cli/doctor/types.py src/scc_cli/doctor/checks/environment.py && uv run ruff check src/scc_cli/core/errors.py src/scc_cli/core/contracts.py src/scc_cli/doctor/types.py src/scc_cli/doctor/checks/environment.py
