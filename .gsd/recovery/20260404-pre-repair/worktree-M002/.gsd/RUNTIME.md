# RUNTIME.md

## Canonical implementation root
- `scc-sync-1.7.3` is the only writable repo for this work.
- The original dirty `scc` tree is archival and rollback evidence only.

## Runtime assumptions for v1
- Plain OCI backend first.
- Docker Engine / OrbStack / Colima-style Docker CLIs are first runtime targets.
- Podman follows on the same contracts after the first Claude/Codex vertical slice is stable.
- Windows support is WSL-first if needed.

## Verification commands
- `uv run ruff check`
- `uv run mypy src/scc_cli`
- `uv run pytest`

## Expected runtime deliverables
- `scc-base`
- `scc-agent-claude`
- `scc-agent-codex`
- `scc-egress-proxy`

## Enforced egress topology
- agent container on internal-only network
- egress proxy as the only component with internal + external attachment
- no host networking
- deny IP literals by default
- deny loopback, private, link-local, and metadata endpoints by default
- proxy ACL evaluates requested host and resolved IP/CIDR
