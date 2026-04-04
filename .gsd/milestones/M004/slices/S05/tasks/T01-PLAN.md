---
estimated_steps: 6
estimated_files: 1
skills_used: []
---

# T01: README truthfulness updates for M004 safety deliverables

Update README.md to truthfully reflect M004 deliverables:

1. Line 85: Update 'Command guardrails' bullet from plugin-only claim to reflect SCC-owned safety engine as the core baseline. Keep plugin mention as an additional layer. Something like: 'Command guardrails — SCC's built-in safety engine blocks destructive git commands and explicit network tools (curl, wget, ssh, scp, sftp, rsync). The scc-safety-net plugin provides additional coverage.'

2. Command table (~line 280): Add `scc support safety-audit` entry: 'Inspect recent safety-check audit events'

3. Enforcement scope section (~line 113): Add a bullet about runtime safety wrappers: 'Runtime safety: SCC-owned wrappers intercept destructive git commands and explicit network tools (curl, wget, ssh, scp, sftp, rsync) inside the container. Wrappers are defense-in-depth — topology and proxy policy remain the hard network control.'

4. Troubleshooting section (~line 382): Add mention of `scc support safety-audit` alongside launch-audit for diagnosing safety-related issues.

5. Verify no stale terms reintroduced — run existing truthfulness tests.

## Inputs

- `src/scc_cli/commands/support.py`
- `src/scc_cli/core/safety_engine.py`
- `tests/test_docs_truthfulness.py`

## Expected Output

- `README.md with updated safety documentation`

## Verification

uv run pytest --rootdir "$PWD" tests/test_docs_truthfulness.py -v && grep -q 'safety-audit' README.md && grep -q 'safety engine' README.md
