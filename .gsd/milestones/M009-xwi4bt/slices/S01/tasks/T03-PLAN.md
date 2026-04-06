---
estimated_steps: 8
estimated_files: 4
skills_used: []
---

# T03: Centralize auth messaging and eliminate auth_bootstrap.py duplication

After T01 and T02, auth_bootstrap.py's ensure_provider_auth is no longer called by any launch site. The auth messaging (non-interactive error text, interactive notice text) is duplicated between auth_bootstrap.py and preflight.py._ensure_auth.

Steps:
1. Verify no callers of ensure_provider_auth remain outside tests: grep -rn 'ensure_provider_auth' src/scc_cli/ should return only the definition and test imports.
2. If no callers remain, delete auth_bootstrap.py or reduce it to a deprecated redirect.
3. If callers remain (e.g. some edge path), make auth_bootstrap.ensure_provider_auth delegate to preflight._ensure_auth.
4. Ensure the canonical auth messaging (error text, notice text) lives only in preflight.py._ensure_auth.
5. Update import boundary tests and allowlists if auth_bootstrap.py is deleted.
6. Run targeted tests and full suite.

## Inputs

- `src/scc_cli/commands/launch/auth_bootstrap.py — to be eliminated or reduced`

## Expected Output

- `auth_bootstrap.py deleted or reduced to redirect`
- `All auth messaging in preflight.py._ensure_auth`
- `No import of ensure_provider_auth in non-test code`

## Verification

grep -rn 'from.*auth_bootstrap' src/scc_cli/ | grep -v __pycache__ && uv run pytest -q
