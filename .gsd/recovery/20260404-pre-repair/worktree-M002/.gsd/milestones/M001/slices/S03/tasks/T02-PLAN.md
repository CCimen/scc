---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T02: Characterize config inheritance and policy merges

Add characterization tests for config inheritance and network-policy merge behavior so later typing work cannot silently change org/team widening or project/user narrowing rules.

## Inputs

- `Existing config tests`
- `REQUIREMENTS.md`
- `Spec 02`
- `Spec 04`

## Expected Output

- `Focused tests locking current config inheritance and policy-merge behavior.`
- `Clear failing diffs if later slices change those rules unintentionally.`

## Verification

uv run pytest tests/test_config_inheritance.py tests/test_effective_config.py
