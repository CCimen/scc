---
estimated_steps: 25
estimated_files: 6
skills_used:
  - karpathy-guidelines
  - writing-clearly-and-concisely
---

# T01: Expose recent launch-audit diagnostics through support surfaces

**Expected skills:** `karpathy-guidelines`, `writing-clearly-and-concisely`.

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

## Inputs

- `src/scc_cli/application/launch/preflight.py`
- `src/scc_cli/adapters/local_audit_event_sink.py`
- `src/scc_cli/application/support_bundle.py`
- `src/scc_cli/commands/support.py`
- `src/scc_cli/kinds.py`
- `README.md`

## Expected Output

- `src/scc_cli/application/launch/audit_log.py`
- `src/scc_cli/application/support_bundle.py`
- `src/scc_cli/commands/support.py`
- `src/scc_cli/kinds.py`
- `src/scc_cli/presentation/json/launch_audit_json.py`
- `tests/test_launch_audit_support.py`
- `tests/test_support_bundle.py`
- `README.md`

## Verification

uv run pytest --rootdir "$PWD" ./tests/test_launch_audit_support.py ./tests/test_support_bundle.py -q

## Observability Impact

Adds `scc support launch-audit` and bundle-manifest launch diagnostics so a future agent can inspect the last failed launch, malformed-record count, and sink destination without opening raw JSONL by hand.
