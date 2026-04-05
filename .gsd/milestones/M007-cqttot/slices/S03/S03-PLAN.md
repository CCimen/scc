# S03: Doctor provider-awareness and typed provider errors

**Goal:** Add auth readiness checking with truthful wording ('cache present' not 'logged in'). Make doctor, sessions, audit, resume, and machine-readable outputs provider-truthful. Add typed provider errors.
**Demo:** After this: scc doctor --provider codex checks Codex readiness specifically. Doctor output groups backend health vs provider readiness. ProviderNotReadyError and ProviderImageMissingError exist with user_message and suggested_action.

## Tasks
