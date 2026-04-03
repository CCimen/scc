# DECISIONS.md

This file is append-only. Record new decisions as new entries.

---

## D-001 — Product identity
SCC means **Sandboxed Coding CLI**.

Status: accepted

---

## D-002 — Product center
SCC is a governed runtime for coding agents, not a new coding agent.

Status: accepted

---

## D-003 — Implementation root
All architecture work happens in `scc-sync-1.7.3`. The dirty `scc` tree is archival only.

Status: accepted

---

## D-004 — Backward compatibility stance
There are no active users, so core code will not carry long-term backward-compatibility aliases after the one-time migration.

Status: accepted

---

## D-005 — First-class providers
V1 supports Claude Code and Codex only. Other providers remain out of scope until the new core is stable.

Status: accepted

---

## D-006 — Runtime strategy
Portable OCI comes first. Docker Desktop is optional and not foundational.

Status: accepted

---

## D-007 — Network widening policy
Only org policy and delegated team policy may widen effective egress. Projects and users may only narrow.

Status: accepted

---

## D-008 — Enforced network scope
V1 enforced egress is HTTP/HTTPS-focused only.

Status: accepted

---

## D-009 — Runtime safety scope
The first cross-agent safety layer governs destructive git plus explicit network tools.

Status: accepted

---

## D-010 — Skills portability
Open Agent Skills are the only intended shared portability surface.

Status: accepted
