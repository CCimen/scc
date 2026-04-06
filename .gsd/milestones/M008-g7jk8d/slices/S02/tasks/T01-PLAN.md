---
estimated_steps: 14
estimated_files: 4
skills_used: []
---

# T01: Audit and fix auth-status vocabulary with three-tier readiness distinction

Audit every user-facing string that describes provider readiness:

1. Doctor output (checks/environment.py, render.py) — currently uses 'auth cache present'
2. Setup summary (setup.py _render_setup_summary, _render_provider_status) — uses what vocabulary?
3. Provider choice prompt (provider_choice.py prompt_for_provider_choice) — uses 'connected' vs 'sign-in required'
4. Auth bootstrap (auth_bootstrap.py) — uses 'auth cache is missing'

Establish canonical three-tier vocabulary:
- 'auth cache present' — when we only check file existence (not 'connected')
- 'image available' — when provider image exists locally (not 'ready')
- 'launch-ready' — only when BOTH auth + image are present

Fix mismatches. In particular:
- provider_choice.py: change 'connected' to 'auth cache present' and 'sign-in required' to 'sign-in needed'
- setup summary: distinguish auth vs image in the completion display
- doctor: keep current vocabulary (already truthful) but add image check alongside auth check in grouped output

Add guardrail test scanning for banned terms ('connected' meaning auth cache, standalone 'ready' meaning only one tier).

## Inputs

- `src/scc_cli/commands/launch/auth_bootstrap.py`
- `src/scc_cli/doctor/render.py`

## Expected Output

- `tests/test_auth_vocabulary_guardrail.py`

## Verification

uv run pytest tests/test_auth_vocabulary_guardrail.py -v && uv run ruff check
