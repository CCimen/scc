# S03 Research: Doctor provider-awareness and typed provider errors

## Summary

This slice adds three capabilities: (1) a `--provider` flag on `scc doctor` that scopes provider-specific checks to a named provider, (2) grouping doctor output into "Backend Health" vs "Provider Readiness" sections, and (3) two new typed errors — `ProviderNotReadyError` and `ProviderImageMissingError` — with `user_message` and `suggested_action`.

This is **targeted research** — known patterns applied to known code with moderate integration surface.

## Requirement Coverage

- **R001 (maintainability):** Typed provider errors replace loose strings/generic exceptions at readiness boundaries. Grouping doctor output makes the diagnostic surface more cohesive.

## Recommendation

Three tasks, low-to-medium risk each:

1. **T01 — Typed errors and AuthReadiness model.** Add `ProviderNotReadyError`, `ProviderImageMissingError`, and `AuthReadiness` dataclass to `core/errors.py` and `core/contracts.py`. Tests for error messages and field population.

2. **T02 — Provider-aware doctor checks and `--provider` flag.** Thread `provider_id` through `run_doctor()` → `check_provider_image()`. Add `check_provider_auth()` function. Add `--provider` option to `doctor_cmd` in `admin.py`. Add `category` field to `CheckResult` for grouping.

3. **T03 — Doctor output grouping and render changes.** Update `render_doctor_results()` to group checks by category. Update `build_doctor_json_data()` to include category. Tests covering grouped output.

## Implementation Landscape

### Files to touch

| File | What changes |
|------|-------------|
| `src/scc_cli/core/errors.py` | Add `ProviderNotReadyError(PrerequisiteError)` and `ProviderImageMissingError(PrerequisiteError)` |
| `src/scc_cli/core/contracts.py` | Add `AuthReadiness` frozen dataclass (per D037: status, mechanism, guidance) |
| `src/scc_cli/doctor/types.py` | Add `category: str = "general"` field to `CheckResult` |
| `src/scc_cli/doctor/checks/environment.py` | (a) `check_provider_image()` accepts explicit `provider_id` param, (b) new `check_provider_auth()` function that checks Docker volume for auth files |
| `src/scc_cli/doctor/core.py` | `run_doctor()` accepts `provider_id: str \| None = None`, passes it to `check_provider_image()` and `check_provider_auth()`, assigns categories to checks |
| `src/scc_cli/doctor/render.py` | `render_doctor_results()` groups checks by category in the table |
| `src/scc_cli/doctor/serialization.py` | `build_doctor_json_data()` includes category field |
| `src/scc_cli/doctor/checks/__init__.py` | Export `check_provider_auth` |
| `src/scc_cli/doctor/__init__.py` | Export `check_provider_auth` |
| `src/scc_cli/commands/admin.py` | Add `--provider` option to `doctor_cmd`, pass to `run_doctor()` and `render_doctor_results()` |

### Existing patterns to follow

**Error types:** Follow `InvalidProviderError` shape — `@dataclass` extending `PrerequisiteError` (exit_code=3), with `provider_id` field and auto-populated `user_message`/`suggested_action` in `__post_init__`. `ProviderNotReadyError` is the general readiness error; `ProviderImageMissingError` is the specific image-not-found case.

**Doctor check functions:** Each returns a `CheckResult`. The `check_provider_image()` already handles provider_id internally via `config.get_selected_provider()`. S03 changes this to accept an explicit parameter: `check_provider_image(provider_id: str | None = None)`, defaulting to the config value when None.

**`--provider` CLI pattern:** Follows the same pattern as `flow.py`'s `--provider` option: `typer.Option(None, "--provider", help="...")`. Value is validated against `KNOWN_PROVIDERS`.

### AuthReadiness model (D037)

```python
@dataclass(frozen=True)
class AuthReadiness:
    status: str       # "missing", "present"  
    mechanism: str    # "oauth_file", "auth_json_file"
    guidance: str     # actionable next step
```

V1 checks file presence only (no validation). The check inspects the provider's Docker data volume for known auth files:
- Claude: `.credentials.json` in `docker-claude-sandbox-data`
- Codex: `auth.json` in `docker-codex-sandbox-data`

The check runs `docker volume inspect <volume>` to see if the volume exists, then `docker run --rm -v <volume>:/check alpine test -f /check/<auth_file>` to probe file existence. This is diagnostic — failures return CheckResult with `passed=False`, not exceptions.

### CheckResult category field

Add `category: str = "general"` to CheckResult. Assign categories in `run_doctor()`:
- `"backend"` — Git, Docker, Docker Daemon, Sandbox Backend, Runtime Backend
- `"provider"` — Provider Image, Provider Auth
- `"config"` — Config Directory, User Config, Safety Policy
- `"worktree"` — Git Worktrees, Worktree Health, Branch Conflicts
- `"general"` — WSL2, Workspace Path, and anything else

`render_doctor_results()` groups by category, rendering section headers between groups.

### Doctor output grouping

Current render is a flat table. The change adds category-based section rows or group headers. The simplest approach: sort checks by category, then render a separator row with the category name when the category changes. This is backward-compatible — JSON output adds a `category` field but doesn't change shape.

### Key constraints

1. **No Docker dependency in tests.** Auth readiness checks must be testable by mocking `subprocess.run` — same pattern as `check_provider_image()`.
2. **Backward compatibility.** `run_doctor()` with no `provider_id` argument must behave identically to current behavior. Category defaults to `"general"` so existing CheckResult construction is unchanged.
3. **D032 compliance.** Doctor is diagnostic — unknown providers in `--provider` get a user-friendly error message, not a crash. Use `KNOWN_PROVIDERS` validation in the CLI command.
4. **S01 dependency.** `check_provider_image()` and `check_provider_auth()` both use `get_runtime_spec()` from the registry (S01 deliverable).

### Risk assessment

**Low risk.** All work follows established patterns. The typed errors are straightforward dataclass additions. The doctor threading is a parameter-passing exercise. The render grouping is cosmetic. No new external dependencies, no architecture changes.
