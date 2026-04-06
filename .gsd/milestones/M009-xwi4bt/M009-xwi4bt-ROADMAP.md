# M009-xwi4bt: Preflight Convergence and Auth Bootstrap Unification

## Vision
Every launch path (start, wizard, worktree, dashboard) uses the same three-function preflight sequence with no structural asymmetry. Auth bootstrap messaging lives in one place. Setup shows three-tier readiness consistently in both the status panel and completion summary.

## Slice Overview
| ID | Slice | Risk | Depends | Done | After this |
|----|-------|------|---------|------|------------|
| S01 | Unify all launch paths on shared preflight and fix auth bootstrap gap | high | — | ✅ | All five launch sites call collect_launch_readiness + ensure_launch_ready. ensure_launch_ready actually calls bootstrap_auth(). auth_bootstrap.py eliminated or trivial. Auth messaging in one place. |
| S02 | Setup three-tier consistency and final verification | low | S01 | ⬜ | setup.py _render_provider_status shows launch-ready/auth cache present/image available/sign-in needed. Same as show_setup_complete. |
