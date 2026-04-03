# M001-RESEARCH.md

# Baseline findings to preserve during refactor

## Codebase reality from prior review
- Provider abstraction is still too Claude-shaped.
- Error and exit-code contracts need alignment.
- Launch and flow orchestration remain larger than they should be.
- Application/config boundaries still rely too heavily on raw dictionaries.
- Runtime detection is still name-based instead of capability-based.
- Complexity guardrails exist but are not yet enforced strongly enough.

## Why Milestone 0 / M001 must come first
If the codebase moves directly into multi-runtime and multi-provider work without a green synced baseline and typed contracts, the product will accumulate more provider leakage and more misleading security surfaces.

## Research conclusion
The best first step is not new runtime code. It is repo truth, vocabulary cleanup, typed core seams, and characterization coverage.
