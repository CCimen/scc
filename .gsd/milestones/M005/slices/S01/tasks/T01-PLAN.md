---
estimated_steps: 25
estimated_files: 1
skills_used: []
---

# T01: Produce comprehensive maintainability audit artifact

Combine the hotspot inventory, boundary-repair map, and robustness-debt catalog into a single comprehensive audit artifact at `.gsd/milestones/M005/slices/S01/MAINTAINABILITY-AUDIT.md`. This artifact is the input for all S02-S06 planning.

The audit must contain three major sections:

**Section 1 — Ranked Hotspot Inventory:**
- Run `find src/scc_cli -name '*.py' | xargs wc -l | sort -rn` to get the live file-size census.
- Produce a ranked table of all files > 300 lines with columns: Rank, File (relative path), Lines, Domain cluster (commands/ui/application/docker/marketplace/core/other), Layer-mixing assessment (Yes/No + brief note).
- Tag each file > 800 lines as MANDATORY-SPLIT. Tag files > 1100 lines as HARD-FAIL.
- Include a top-10 largest functions table using AST analysis: `import ast; for each top file, parse and find functions > 150 lines`.

**Section 2 — Boundary-Repair Map:**
- Scan for docker imports outside adapter/runtime seams: `grep -rn 'from scc_cli.docker' src/scc_cli/ | grep -v 'adapters/' | grep -v 'docker/'`
- Scan for core-to-marketplace leakage: `grep -rn 'from scc_cli.marketplace' src/scc_cli/core/`
- Scan for presentation-to-runtime coupling: `grep -rn 'from.*console' src/scc_cli/docker/`
- Identify import cycles: check docker.core -> docker.launch and similar bidirectional imports.
- Catalog Claude-specific shapes in marketplace pipeline: files referencing `.claude`, `claude-plugins-official`, Claude-specific paths.
- Present all findings in a table with columns: Source file:line, Import target, Violation type, Severity.

**Section 3 — Robustness-Debt Catalog:**
- Count and list all `except Exception` sites: `grep -rn 'except Exception' src/scc_cli/` grouped by file with severity (HIGH for runtime/credential/docker ops, MEDIUM for application logic, LOW for cleanup/diagnostic).
- Count and list unchecked subprocess calls: `grep -rn 'subprocess.run' src/scc_cli/` — note which use `check=True`, which capture stderr, which set timeouts.
- Identify mutable module-level defaults: `grep -rn 'DEFAULT_\|_DEFAULTS\|DETECTION_ORDER\|INSTALL_COMMANDS\|BLOCK_MESSAGES\|_RULE_NAMES\|_NETWORK_POLICY' src/scc_cli/` — assess mutability risk.
- Count typing debt: `dict[str, Any]` references, `cast()` calls, `TypeAlias = dict` patterns.
- List existing quality xfails from test files with what each masks.

Constraints:
- Do NOT modify any production code.
- All numbers must come from live codebase scans, not copied from the research doc (though the research doc confirms what to expect).
- Use markdown tables for all structured data.
- End the document with a 'Priority Queue for S02-S06' section that ranks the top-20 action items across all three categories.

## Inputs

- `src/scc_cli/`

## Expected Output

- `.gsd/milestones/M005/slices/S01/MAINTAINABILITY-AUDIT.md`

## Verification

test -f .gsd/milestones/M005/slices/S01/MAINTAINABILITY-AUDIT.md && grep -c '^|' .gsd/milestones/M005/slices/S01/MAINTAINABILITY-AUDIT.md | xargs test 20 -le
