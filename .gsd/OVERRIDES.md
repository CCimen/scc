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
**Scope:** active
**Applied-at:** M003/S04/T03

---
