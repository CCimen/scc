# S03: Doctor provider-awareness and typed provider errors

**Goal:** scc doctor is provider-aware: `--provider` flag scopes checks, output groups by category (backend/provider/config/worktree), and two typed provider errors (ProviderNotReadyError, ProviderImageMissingError) exist with actionable messages.
**Demo:** After this: scc doctor --provider codex checks Codex readiness specifically. Doctor output groups backend health vs provider readiness. ProviderNotReadyError and ProviderImageMissingError exist with user_message and suggested_action.

## Tasks
- [x] **T01: Added ProviderNotReadyError, ProviderImageMissingError, AuthReadiness dataclass, CheckResult.category field, and check_provider_auth() with 23 passing tests** — Pure additive task — add all new types and one new check function. No changes to existing control flow.

1. Add ProviderNotReadyError(PrerequisiteError) and ProviderImageMissingError(PrerequisiteError) to core/errors.py. Both carry provider_id field and auto-populate user_message/suggested_action in __post_init__. ProviderNotReadyError is the general readiness error (exit_code=3). ProviderImageMissingError is the specific image-not-found case (exit_code=3). Follow InvalidProviderError pattern.

2. Add AuthReadiness frozen dataclass to core/contracts.py with fields: status (str — 'missing' or 'present'), mechanism (str — 'oauth_file' or 'auth_json_file'), guidance (str — actionable next step).

3. Add `category: str = 'general'` field to CheckResult in doctor/types.py. Default ensures backward compatibility.

4. Add check_provider_auth(provider_id: str | None = None) to doctor/checks/environment.py. Logic: resolve provider via get_runtime_spec(), determine auth file name (.credentials.json for claude, auth.json for codex), run `docker volume inspect <volume>` then `docker run --rm -v <volume>:/check alpine test -f /check/<auth_file>` via subprocess.run (mocked in tests). Return CheckResult with passed=True/False and category='provider'. Export from doctor/checks/__init__.py.

5. Write tests in tests/test_doctor_provider_errors.py: ProviderNotReadyError message/action/exit_code, ProviderImageMissingError message/action/exit_code, AuthReadiness field access, check_provider_auth happy path, check_provider_auth missing auth, check_provider_auth volume missing, check_provider_auth subprocess timeout, check_provider_auth unknown provider fallback, CheckResult category default.
  - Estimate: 45m
  - Files: src/scc_cli/core/errors.py, src/scc_cli/core/contracts.py, src/scc_cli/doctor/types.py, src/scc_cli/doctor/checks/environment.py, src/scc_cli/doctor/checks/__init__.py, tests/test_doctor_provider_errors.py
  - Verify: uv run pytest tests/test_doctor_provider_errors.py -v && uv run mypy src/scc_cli/core/errors.py src/scc_cli/core/contracts.py src/scc_cli/doctor/types.py src/scc_cli/doctor/checks/environment.py && uv run ruff check src/scc_cli/core/errors.py src/scc_cli/core/contracts.py src/scc_cli/doctor/types.py src/scc_cli/doctor/checks/environment.py
- [x] **T02: Wired --provider flag, category assignment, and grouped doctor output with 20 new tests** — Wire all T01 additions into the existing doctor flow: threading provider_id, CLI flag, category assignment, and grouped rendering.

1. Update run_doctor() in doctor/core.py: add `provider_id: str | None = None` parameter. Pass provider_id to check_provider_image(provider_id=provider_id). Call check_provider_auth(provider_id=provider_id) when docker_ok (same guard as check_provider_image). Assign category to each CheckResult after construction: 'backend' for Git/Docker/Docker Daemon/Sandbox Backend/Runtime Backend, 'provider' for Provider Image/Provider Auth, 'config' for Config Directory/User Config/Safety Policy, 'worktree' for Git Worktrees/Worktree Health/Branch Conflicts, 'general' for WSL2/Workspace Path and anything else.

2. Update check_provider_image() in environment.py: add `provider_id: str | None = None` parameter. When provided, use it directly instead of reading from config. Set result.category = 'provider' on all return paths.

3. Add `--provider` option to doctor_cmd in admin.py: `provider: str | None = typer.Option(None, '--provider', help='Check readiness for a specific provider')`. Validate against KNOWN_PROVIDERS — if invalid, print error and raise typer.Exit(2). Pass provider_id to run_doctor() and render_doctor_results().

4. Update render_doctor_results() in doctor/render.py: sort checks by category order (backend → provider → config → worktree → general). Add category section header rows in the table when category changes. Category headers use bold cyan style.

5. Update build_doctor_json_data() in doctor/serialization.py: add 'category' field to each check dict.

6. Update exports: add check_provider_auth to doctor/__init__.py __all__.

7. Write tests in tests/test_doctor_provider_wiring.py: run_doctor() with provider_id passes it to check_provider_image, run_doctor() with provider_id calls check_provider_auth, run_doctor() assigns categories correctly, doctor_cmd --provider validates against KNOWN_PROVIDERS, doctor_cmd --provider unknown exits with error, build_doctor_json_data includes category, render_doctor_results groups by category (check table row order).
  - Estimate: 60m
  - Files: src/scc_cli/doctor/core.py, src/scc_cli/doctor/checks/environment.py, src/scc_cli/commands/admin.py, src/scc_cli/doctor/render.py, src/scc_cli/doctor/serialization.py, src/scc_cli/doctor/__init__.py, tests/test_doctor_provider_wiring.py
  - Verify: uv run pytest tests/test_doctor_provider_wiring.py tests/test_doctor_provider_errors.py tests/test_doctor_image_check.py tests/test_doctor_checks.py -v && uv run mypy src/scc_cli/doctor/core.py src/scc_cli/doctor/render.py src/scc_cli/doctor/serialization.py src/scc_cli/commands/admin.py && uv run ruff check src/scc_cli/doctor/ src/scc_cli/commands/admin.py && uv run pytest -q
