# M016 - Enterprise Audit And Compliance Bundle MVP

## Goal
Give municipalities, agencies, and companies a deterministic audit evidence
bundle they can inspect during SCC evaluation without adding an enterprise
control plane too early.

## Non-goals
- Do not implement SSO, SCIM, credential broker, or admin-console behavior.
- Do not add an enterprise dashboard or project registry.
- Do not add new providers.
- Do not add Docker socket access or devcontainer/Compose network attachment.
- Do not add SBOM automation until the evidence bundle shape is stable.
- Do not claim external certification such as SOC 2 or ISO 27001.

## Canonical Owners
- Bundle manifest and archive: `src/scc_cli/application/support_bundle.py`
- CLI surface: `src/scc_cli/commands/support.py`
- Launch audit evidence: `src/scc_cli/application/launch/audit_log.py`
- Safety audit evidence: `src/scc_cli/application/safety_audit.py`
- Docs claim truth: `../scc-cli-docs/src/content/docs/reference/docs-claim-map.mdx`

## Roadmap

| Slice | Status | Name | Scope | Done when |
| --- | --- | --- | --- | --- |
| S00 | Done | Source-of-truth decision | Record D058 and this milestone file | M016 starts from existing support-bundle owners and avoids duplicate pipelines. |
| S01 | Done | Compliance profile | Add `scc support bundle --compliance` | Existing support bundles can emit `enterprise_audit_v1` evidence index and checksums over redacted manifest sections. |
| S02 | Planned | Evidence hardening | Add only missing evidence from existing owners | The profile remains deterministic and docs-truth backed without adding dashboard/identity/SBOM scope. |
| S03 | Planned | Pilot validation | Exercise the compliance profile in the enterprise pilot journey | Docs explain what the evidence proves and what remains future. |

## S01 Acceptance
- Default support bundles remain unchanged.
- `--compliance` adds a `compliance` manifest section with profile,
  schema version, evidence index, section checksums, and non-goals.
- Checksums are computed from emitted redacted manifest sections.
- Docs describe this as audit evidence, not certification.
- Tests cover default/no-profile behavior, profile output, checksum stability,
  redaction interaction, and CLI flag wiring.
