# Spec 05 — Safety Engine

## Objective
Provide one cross-agent runtime safety baseline.

## Shared contract
`SafetyEngine.evaluate(...) -> SafetyVerdict`

## V1 command families
- destructive git
- explicit network tools: `curl`, `wget`, `ssh`, `scp`, `sftp`, `rsync` with remote target

## Rules
- fail closed when policy cannot be loaded or validated
- runtime wrappers are the hard cross-agent baseline
- provider-native integrations improve UX and audit context only
