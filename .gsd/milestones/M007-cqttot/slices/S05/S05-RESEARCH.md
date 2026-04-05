# S05 Research: Product naming, documentation truthfulness, and milestone validation

## Summary

Straightforward slice — product naming fix is a 2-file text change, truthfulness guardrails follow the established `test_docs_truthfulness.py` and `test_provider_branding.py` patterns, and milestone validation is procedural.

## Recommendation

Three tasks: (T01) README and pyproject.toml naming fix + expanded truthfulness guardrail tests, (T02) milestone validation, (T03) milestone completion. T01 is the only code task. T02 and T03 are procedural GSD ceremony.

## Implementation Landscape

### Current state of product naming

**Already correct (no changes needed):**
- All Python source uses "Sandboxed Code CLI" consistently — `__init__.py`, `cli.py`, `setup_ui.py`, `setup.py`, `theme.py`, `errors.py`, `branding.py`, `commands/init.py` (12 occurrences)
- `test_provider_branding.py` already asserts "Sandboxed Code CLI" in version headers and guards against "Claude Code" in non-adapter modules
- `ProviderRuntimeSpec` in `core/provider_registry.py` uses `display_name="Claude Code"` and `display_name="Codex"` — these are factual provider names, not product branding (already in `_ALLOWED_FILES` in the branding guardrail)
- Constitution uses "SCC" throughout, no "Sandboxed" mention

**Needs fixing (2 files, 3 lines):**

| File | Line | Current | Target |
|------|------|---------|--------|
| `README.md` | 1 | `SCC - Sandboxed Claude CLI` | `SCC - Sandboxed Code CLI` |
| `pyproject.toml` | 8 | `"Run Claude Code in Docker sandboxes with team configs..."` | `"Run AI coding agents in Docker sandboxes with team configs..."` (or similar provider-neutral phrasing) |

**README Claude references that are legitimate (keep as-is):**
- Line 24: "Run Claude Code..." — factual description of current primary provider. Could optionally add "(and Codex)" but this is a README editorial choice, not a truthfulness violation
- Line 28: "Extend Claude with..." — marketplace is still Claude-plugin shaped per KNOWLEDGE
- Line 51: "Press Shift+Tab inside Claude..." — Claude-specific UX instruction
- Line 86: "while Claude experiments" — colloquial, but in a Claude Code user guide section

The README's Claude-specific prose in the body is accurate for the current user base. Making the entire README provider-neutral is out of scope for S05 — that's a docs rewrite. S05 fixes the **product name** in the title and package description per D030.

### Truthfulness guardrail expansion for M007

The existing `test_docs_truthfulness.py` covers M003 vocabulary, M004 safety engine, and M005 team-pack model. M007 needs guardrails for:

1. **Product naming** — README title must say "Sandboxed Code CLI", not "Sandboxed Claude CLI" or "Sandboxed Coding CLI"
2. **ProviderRuntimeSpec exists** — `core/provider_registry.py` and `core/contracts.py` must contain the registry and spec type
3. **Fail-closed dispatch** — `core/errors.py` must define `InvalidProviderError`
4. **Doctor provider-awareness** — `doctor/checks/environment.py` must define `check_provider_auth`
5. **Legacy constant cleanup** — `core/constants.py` must NOT contain Claude-specific constants (already covered by `test_no_claude_constants_in_core.py` — can reference in truthfulness test or leave as-is)

The branding guardrail in `test_provider_branding.py` already covers most naming concerns. The new truthfulness tests should extend `test_docs_truthfulness.py` with an M007 section.

### D001 / D030 status

D030 already records the canonical product name decision: "SCC — Sandboxed Code CLI." D001 (from M001/S04) is about typed seams, not naming. The roadmap's "D-001 updated" likely refers to an older naming decision that predates the current decision numbering. Since D030 already exists, no new decision is needed — just the code changes to make reality match D030.

### Milestone validation scope

M007 has 5 slices, S01–S04 complete with passing verification. S05 is the final slice. After T01 (code changes), the milestone validation process is:
- Full test suite pass
- Ruff + mypy clean
- Success criteria checklist from ROADMAP
- Slice delivery audit
- Cross-slice integration check
- Requirement coverage

### Files to touch

**T01 — Naming fix + truthfulness guardrails:**
- `README.md` — line 1 title fix
- `pyproject.toml` — line 8 description fix
- `tests/test_docs_truthfulness.py` — add M007 truthfulness guardrail section (4–6 new tests)

**T02 — Milestone validation:** procedural (gsd_validate_milestone)
**T03 — Milestone completion:** procedural (gsd_complete_milestone)

### Test count baseline

Current: 4745 collected. S05 should add ~4–6 truthfulness tests → ~4749–4751.

### Constraints

- README body Claude references (lines 24, 28, 51, 86) are factual for current state and should NOT be made provider-neutral in S05. That's a separate docs milestone.
- pyproject.toml keywords include "claude" — this is acceptable for discoverability (users search for "claude docker cli")
- The `test_provider_branding.py` guardrail already prevents "Claude Code" in non-adapter Python modules and "Sandboxed Claude" anywhere in non-adapter code

### No external dependencies or unfamiliar technology

All patterns are established. No skills needed. No library lookups needed.
