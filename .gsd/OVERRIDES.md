# GSD Overrides

User-issued overrides that supersede plan document content.

---
## Override: 2026-04-03T21:37:02.620Z

**Change:** Keep milestone order M002 -> M003 -> M004 -> M005.
  Do not promote M005 ahead of M003 or M004.
  In M002-M004, allow only local maintainability extractions that directly enable the active slice in touched files.
  Reserve repo-wide decomposition, typed config migration, guardrail restoration, xfail removal, and the broad coverage campaign for M005.
  When reassessing the roadmap, preserve M005 as the final quality-bar milestone
**Scope:** resolved
**Applied-at:** M002/S05/none

---

## Override: 2026-04-03T21:40:41.015Z

**Change:** After M002 completes, do not start M005 next.
  Create/register M003 and M004 from PLAN.md and run milestones in this order:
  M003 -> M004 -> M005.

  M003 = Portable Runtime And Enforced Web Egress.
  M004 = Cross-Agent Runtime Safety.
  M005 = Architecture Quality, Strictness, And Hardening.

  Keep M005 as the final quality-bar milestone.
  In M003 and M004, allow only local maintainability extractions that directly enable the active slice in touched files.
  Do not pull repo-wide decomposition, broad typed-config migration, guardrail restoration, xfail removal, or the large coverage campaign forward before M005.
**Scope:** resolved
**Applied-at:** M002/S05/none

---

## Override: 2026-04-04T10:29:52.388Z

**Change:** For the rest of M003, keep the enterprise egress model explicit:
  - web-egress-enforced is the normal cloud-provider enterprise mode
  - locked-down-web is an intentional no-web / no-cloud-launch posture unless a future local-model path exists
  - org owns baseline mode, hard deny overlays, named destination sets, and delegation
  - teams may widen only within delegated bounds
  - project/user scopes may narrow only
  - every workspace/session has exactly one active team context
  - users switch context between teams such as Draken and Eneo; do not implicitly union team allowlists
  - diagnostics must show active team context, effective destination sets, runtime backend, network mode, and clear blocked reasons
  - topology plus proxy policy remain the hard control; wrappers are defense-in-depth, UX, and audit only
**Scope:** resolved
**Applied-at:** M003/S04/T03

---

## Override: 2026-04-04T11:54:39.634Z

**Change:** For M004/S02-S05, keep the safety architecture narrow and truthful.

  S02:
  - Put the first SCC-owned runtime wrappers in scc-base.
  - Scope is destructive git plus explicit network tools only: curl, wget, ssh, scp, sftp, remote rsync.
  - Keep wrappers small, typed, and fail-closed.
  - Do not expand to package managers, cloud CLIs, kubectl, terraform, or broad command families.

  Cross-slice rules:
  - In enforced web-egress modes, topology plus proxy policy remain the hard network control.
  - Network-tool wrappers are defense-in-depth, early UX, and audit only.
  - Do not imply wrappers are the primary enforcement plane for network isolation.
  - Keep provider-native integrations adapter-owned and additive only.
  - Keep one active team context per session/workspace in diagnostics and safety surfaces; no implicit union of team access.
  - Keep M004 maintainability work local to touched files; do not pull M005-style broad cleanup forward.
**Scope:** resolved
**Applied-at:** M004/S02/none

---
