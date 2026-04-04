---
estimated_steps: 26
estimated_files: 7
skills_used:
  - karpathy-guidelines
  - writing-clearly-and-concisely
---

# T02: Converge support-bundle generation on one application-owned implementation

**Expected skills:** `karpathy-guidelines`, `writing-clearly-and-concisely`.

The new diagnostics surface will stay brittle if SCC continues to maintain both `src/scc_cli/support_bundle.py` and `src/scc_cli/application/support_bundle.py`. Route bundle generation, default-path calculation, and settings-driven bundle creation through the application-layer use case, then remove the duplicated top-level helper and its root-sprawl allowance. Preserve existing CLI and settings-screen behavior while keeping the launch-audit summary from T01 on the shared code path.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| settings support-bundle action in `application/settings/use_cases.py` | return a typed settings error and leave no partial success state | N/A | surface invalid payload usage as a settings-action error instead of writing a partial bundle |
| archive writer / output path | fail the request cleanly and preserve the caller's selected output path for retry | N/A | reject partial manifest writes through the existing support-bundle error boundary |
| imports pointing at `scc_cli.support_bundle` | fail loudly in tests and remove the legacy path rather than adding another compatibility wrapper | N/A | N/A |

## Load Profile

- **Shared resources**: one support-bundle manifest build plus one archive write.
- **Per-operation cost**: config reads, doctor execution, bounded audit-summary loading, and one zip manifest write.
- **10x breakpoint**: repeated bundle generation is dominated by doctor and file IO, so the implementation must remain single-path and avoid duplicated manifest assembly.

## Negative Tests

- **Malformed inputs**: missing settings payload, invalid custom output path, and disabled path-redaction flags.
- **Error paths**: doctor failure, archive-writer failure, and missing user/org config files.
- **Boundary conditions**: JSON manifest mode creates no zip, settings-screen bundle generation uses the same default-path helper as the CLI, and no production code imports the removed helper.

## Steps

1. Move any remaining bundle-path or creation helpers needed by CLI/settings into `src/scc_cli/application/support_bundle.py` (or a nearby application helper) so one implementation owns manifest assembly and writing.
2. Update `src/scc_cli/application/settings/use_cases.py`, `src/scc_cli/ui/settings.py`, and the support command to call that shared application path rather than `src/scc_cli/support_bundle.py`.
3. Delete the legacy top-level helper, remove its allowlist entry from `tests/test_no_root_sprawl.py`, and adjust tests to target the shared application implementation.
4. Run focused settings/support/root-sprawl coverage to prove the repo now has one support-bundle source of truth.

## Must-Haves

- [ ] CLI support-bundle generation and settings-screen support-bundle generation call the same application-owned implementation.
- [ ] The launch-audit summary from T01 stays present after the convergence work.
- [ ] `src/scc_cli/support_bundle.py` is removed instead of becoming another compatibility shim.
- [ ] Root-sprawl and focused settings/support tests fail if a future refactor reintroduces duplicate support-bundle logic.

## Inputs

- `src/scc_cli/application/support_bundle.py`
- `src/scc_cli/application/settings/use_cases.py`
- `src/scc_cli/ui/settings.py`
- `src/scc_cli/commands/support.py`
- `src/scc_cli/support_bundle.py`
- `tests/test_application_settings.py`
- `tests/test_support_bundle.py`
- `tests/test_no_root_sprawl.py`

## Expected Output

- `src/scc_cli/application/support_bundle.py`
- `src/scc_cli/application/settings/use_cases.py`
- `src/scc_cli/ui/settings.py`
- `src/scc_cli/commands/support.py`
- `src/scc_cli/support_bundle.py`
- `tests/test_application_settings.py`
- `tests/test_support_bundle.py`
- `tests/test_no_root_sprawl.py`

## Verification

uv run pytest --rootdir "$PWD" ./tests/test_application_settings.py ./tests/test_support_bundle.py ./tests/test_no_root_sprawl.py -q
