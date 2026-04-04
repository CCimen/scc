---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T03: Characterize current safety-net behavior

Inspect the current safety-net coverage and add characterization tests around the current destructive-git and explicit-network-tool protections that M001 names as the first cross-agent safety layer.

## Inputs

- `Existing safety-related tests`
- `Spec 05`

## Expected Output

- `Characterization coverage for current safety-net behavior.`
- `A stable base for later shared SafetyEngine extraction.`

## Verification

uv run pytest -k "safety or git or network tool or curl or ssh"
