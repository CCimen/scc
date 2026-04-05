---
estimated_steps: 8
estimated_files: 7
skills_used: []
---

# T02: Wire --provider flag, category assignment, and grouped doctor output

Wire all T01 additions into the existing doctor flow: threading provider_id, CLI flag, category assignment, and grouped rendering.

1. Update run_doctor() in doctor/core.py: add `provider_id: str | None = None` parameter. Pass provider_id to check_provider_image(provider_id=provider_id). Call check_provider_auth(provider_id=provider_id) when docker_ok (same guard as check_provider_image). Assign category to each CheckResult after construction: 'backend' for Git/Docker/Docker Daemon/Sandbox Backend/Runtime Backend, 'provider' for Provider Image/Provider Auth, 'config' for Config Directory/User Config/Safety Policy, 'worktree' for Git Worktrees/Worktree Health/Branch Conflicts, 'general' for WSL2/Workspace Path and anything else.

2. Update check_provider_image() in environment.py: add `provider_id: str | None = None` parameter. When provided, use it directly instead of reading from config. Set result.category = 'provider' on all return paths.

3. Add `--provider` option to doctor_cmd in admin.py: `provider: str | None = typer.Option(None, '--provider', help='Check readiness for a specific provider')`. Validate against KNOWN_PROVIDERS — if invalid, print error and raise typer.Exit(2). Pass provider_id to run_doctor() and render_doctor_results().

4. Update render_doctor_results() in doctor/render.py: sort checks by category order (backend → provider → config → worktree → general). Add category section header rows in the table when category changes. Category headers use bold cyan style.

5. Update build_doctor_json_data() in doctor/serialization.py: add 'category' field to each check dict.

6. Update exports: add check_provider_auth to doctor/__init__.py __all__.

7. Write tests in tests/test_doctor_provider_wiring.py: run_doctor() with provider_id passes it to check_provider_image, run_doctor() with provider_id calls check_provider_auth, run_doctor() assigns categories correctly, doctor_cmd --provider validates against KNOWN_PROVIDERS, doctor_cmd --provider unknown exits with error, build_doctor_json_data includes category, render_doctor_results groups by category (check table row order).

## Inputs

- ``src/scc_cli/core/errors.py` — ProviderNotReadyError, ProviderImageMissingError from T01`
- ``src/scc_cli/core/contracts.py` — AuthReadiness from T01`
- ``src/scc_cli/doctor/types.py` — CheckResult.category from T01`
- ``src/scc_cli/doctor/checks/environment.py` — check_provider_auth() from T01`
- ``src/scc_cli/doctor/core.py` — existing run_doctor() to modify`
- ``src/scc_cli/doctor/render.py` — existing render_doctor_results() to modify`
- ``src/scc_cli/doctor/serialization.py` — existing build_doctor_json_data() to modify`
- ``src/scc_cli/commands/admin.py` — existing doctor_cmd to add --provider flag`
- ``src/scc_cli/core/provider_resolution.py` — KNOWN_PROVIDERS for CLI validation`

## Expected Output

- ``src/scc_cli/doctor/core.py` — run_doctor() accepts provider_id, threads it, assigns categories`
- ``src/scc_cli/doctor/checks/environment.py` — check_provider_image() accepts provider_id parameter`
- ``src/scc_cli/commands/admin.py` — doctor_cmd has --provider option with validation`
- ``src/scc_cli/doctor/render.py` — render_doctor_results() groups by category with section headers`
- ``src/scc_cli/doctor/serialization.py` — build_doctor_json_data() includes category`
- ``src/scc_cli/doctor/__init__.py` — check_provider_auth in __all__`
- ``tests/test_doctor_provider_wiring.py` — ~10 tests covering wiring, CLI flag, grouping, and serialization`

## Verification

uv run pytest tests/test_doctor_provider_wiring.py tests/test_doctor_provider_errors.py tests/test_doctor_image_check.py tests/test_doctor_checks.py -v && uv run mypy src/scc_cli/doctor/core.py src/scc_cli/doctor/render.py src/scc_cli/doctor/serialization.py src/scc_cli/commands/admin.py && uv run ruff check src/scc_cli/doctor/ src/scc_cli/commands/admin.py && uv run pytest -q
