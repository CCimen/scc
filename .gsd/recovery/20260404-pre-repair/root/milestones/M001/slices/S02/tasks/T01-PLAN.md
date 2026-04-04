---
estimated_steps: 1
estimated_files: 5
skills_used: []
---

# T01: Map legacy network vocabulary surfaces

Search the repo for legacy network mode terms and classify each occurrence by surface: core contract, schema/config parsing, example fixture, test expectation, docs copy, or unrelated English prose. Use the inventory to define the smallest safe migration order.

## Inputs

- `S01 baseline inventory`
- `Spec 01`
- `Spec 04`

## Expected Output

- `A classified inventory of legacy naming surfaces.`
- `A migration order that avoids semantic breakage.`

## Verification

rg -n "unrestricted|corp-proxy-only|isolated" . --glob '!**/.venv/**'
