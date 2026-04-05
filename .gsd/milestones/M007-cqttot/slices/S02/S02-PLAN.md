# S02: Session, resume, and machine-readable output provider hardening

**Goal:** Make settings serialization provider-owned. Implement config ownership model (D041): SCC writes its own layer using provider-native precedence, never overwrites user config. Enforce config freshness (D042). Add runtime permission normalization (D039). Set Codex launch policy (D033) and auth storage (D040). Write state marker. Harden Dockerfiles.
**Demo:** After this: sessions.get_claude_sessions_dir renamed to provider-parameterized helper. audit.py derives path from provider. sandbox.py records provider_id='claude'. Quick Resume shows provider_id. Session list CLI displays provider column.

## Tasks
