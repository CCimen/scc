# S05: Hardening, diagnostics, and decomposition follow-through

**Goal:** Lock the new architecture in place with diagnostics, targeted decomposition, and tests before moving on to runtime/network work.
**Demo:** After this: TBD

## Tasks
- [x] **T01: Added `scc support launch-audit` and redacted recent launch-audit summaries in support bundles.** — **Expected skills:** `karpathy-guidelines`, `writing-clearly-and-concisely`.

Make the durable S04 JSONL sink inspectable without asking operators to open raw files. Add a typed audit-log reader that safely tails the configured file, counts malformed lines, redacts home-directory paths, and powers a new `scc support launch-audit` surface in human and JSON modes. Fold a redacted recent-launch summary into support bundle manifests and update the README command/troubleshooting guidance so the new inspection path is discoverable. Keep the JSONL file append-only and treat it as the source of truth rather than inventing a second persistence format.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| configured launch-audit file at `config.LAUNCH_AUDIT_FILE` | show an explicit unavailable/empty diagnostic state and keep support-bundle generation alive | N/A | skip bad lines, count them, and surface the last malformed line number instead of crashing the reader |
| support-bundle doctor/config collection | keep the manifest valid and attach an error field for the failing section | N/A | preserve the launch-audit summary even if another manifest section fails |

## Load Profile

- **Shared resources**: one append-only local JSONL file plus support-bundle manifest generation.
- **Per-operation cost**: a bounded tail read of recent audit lines, JSON decoding, and one manifest enrichment pass.
- **10x breakpoint**: very large audit logs make naive full-file scans too expensive, so the reader must stay bounded to recent entries.

## Negative Tests

- **Malformed inputs**: missing file, empty file, malformed JSON lines, invalid UTF-8 replacement text, and limit values at `0/1/N`.
- **Error paths**: unreadable audit file, missing bundle dependencies, and JSON output mode when the sink has never been created.
- **Boundary conditions**: all-success logs with no failures, mixed provider ids, and redaction of home-directory paths inside metadata fields.

## Steps

1. Add an application-level launch-audit reader/summarizer that parses the configured JSONL sink into a bounded, redaction-aware diagnostics model.
2. Expose that model through `src/scc_cli/commands/support.py` in both human and JSON modes with a stable JSON envelope kind.
3. Extend `src/scc_cli/application/support_bundle.py` so support bundles include a redacted recent-launch summary rather than raw unbounded log contents.
4. Add focused tests for the reader, CLI surface, and bundle manifest, then update `README.md` command/troubleshooting docs to point to the new diagnostics flow.

## Must-Haves

- [ ] `scc support launch-audit` reports recent launch events, last-failure context, and malformed-record counts from the configured sink.
- [ ] JSON output uses a stable envelope kind and stays redaction-safe by default.
- [ ] Support bundles include launch-audit diagnostics without copying the entire raw JSONL file into the manifest.
- [ ] README troubleshooting/command docs mention the new inspection surface and its purpose.
  - Estimate: 90m
  - Files: src/scc_cli/application/launch/preflight.py, src/scc_cli/adapters/local_audit_event_sink.py, src/scc_cli/application/support_bundle.py, src/scc_cli/commands/support.py, src/scc_cli/kinds.py, README.md
  - Verify: uv run pytest --rootdir "$PWD" ./tests/test_launch_audit_support.py ./tests/test_support_bundle.py -q
- [x] **T02: Unified CLI and settings support-bundle generation on the application support-bundle use case.** — **Expected skills:** `karpathy-guidelines`, `writing-clearly-and-concisely`.

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
  - Estimate: 75m
  - Files: src/scc_cli/application/support_bundle.py, src/scc_cli/application/settings/use_cases.py, src/scc_cli/ui/settings.py, src/scc_cli/commands/support.py, tests/test_application_settings.py, tests/test_support_bundle.py, tests/test_no_root_sprawl.py
  - Verify: uv run pytest --rootdir "$PWD" ./tests/test_application_settings.py ./tests/test_support_bundle.py ./tests/test_no_root_sprawl.py -q
- [x] **T03: Extracted launch-wizard quick-resume and workspace-resume flows into typed helpers with hotspot guardrails.** — **Expected skills:** `karpathy-guidelines`.

`interactive_start` is still the largest launch-flow hotspot in the repo. Split its quick-resume and workspace-resume subflows into explicit helper functions/modules that receive typed context instead of closing over large chunks of mutable local state. Keep prompt behavior, back/cancel semantics, and team-selection precedence identical, then add a targeted hotspot guardrail test so the extraction becomes a durable maintainability win instead of a one-off cleanup.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `render_start_wizard_prompt(...)` answers | preserve BACK/CANCEL/SWITCH_TEAM semantics exactly and localize any regression through focused wizard characterization tests | N/A | reject impossible answer shapes in helper tests instead of silently taking the wrong branch |
| quick-resume context loading/filtering | fall back to new-session flow rather than resuming the wrong workspace/team | N/A | treat incomplete context records as non-matching and continue the wizard safely |
| selected-profile / team-override precedence | preserve the existing `--team` over `selected_profile` rule when helpers rebuild wizard state | N/A | keep mismatched team/workspace context from leaking across resets |

## Load Profile

- **Shared resources**: in-memory recent-context lists and wizard state only.
- **Per-operation cost**: linear filtering of recent contexts plus prompt rendering.
- **10x breakpoint**: very large recent-context lists make quick-resume sluggish, so extracted helpers must keep filtering bounded and side-effect free.

## Negative Tests

- **Malformed inputs**: empty recent-context lists, missing team values, and incomplete workspace context records.
- **Error paths**: cross-team resume rejected at confirmation, workspace quick-resume back-navigation, and team-switch resets.
- **Boundary conditions**: no contexts, single matching context, multiple teams with `show_all_teams`, and standalone mode with no team selection.

## Steps

1. Identify the nested quick-resume/workspace-resume helpers inside `interactive_start` and move them into one or more small module-level helpers with explicit typed inputs.
2. Update `flow.py` and `flow_types.py` so `interactive_start` delegates those branches instead of keeping large nested closures.
3. Add or extend focused wizard characterization tests plus one targeted hotspot guardrail test that measures the extracted maintainability boundary directly.
4. Run the focused wizard/guardrail tests and fix any behavior drift before handoff.

## Must-Haves

- [ ] `interactive_start` delegates quick-resume/workspace-resume logic to typed helpers rather than defining the full subflows inline.
- [ ] Existing quick-resume, cross-team resume, and workspace-resume behaviors stay green under focused characterization tests.
- [ ] A new targeted guardrail test fails if the extracted hotspot grows back past the agreed slice boundary.
- [ ] The extraction reduces local complexity without introducing new adapter imports or changing launch semantics.
  - Estimate: 90m
  - Files: src/scc_cli/commands/launch/flow.py, src/scc_cli/commands/launch/flow_types.py, tests/test_start_wizard_quick_resume_flow.py, tests/test_start_wizard_workspace_quick_resume.py, tests/test_start_cross_team_resume_prompt.py
  - Verify: uv run pytest --rootdir "$PWD" ./tests/test_launch_flow_hotspots.py ./tests/test_start_wizard_quick_resume_flow.py ./tests/test_start_wizard_workspace_quick_resume.py ./tests/test_start_cross_team_resume_prompt.py -q
