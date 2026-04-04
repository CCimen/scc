# S02 — Research: Runtime wrapper baseline in `scc-base`

**Date:** 2026-04-04

## Summary

S02 puts the first SCC-owned runtime wrappers into the `scc-base` Docker image. These wrappers intercept `git`, `curl`, `wget`, `ssh`, `scp`, `sftp`, and `rsync` invocations inside the container, evaluate them against a safety policy using the same logic as the `DefaultSafetyEngine` from S01, and block or allow accordingly. This is the "hard cross-agent baseline" that Constitution §9 requires — it works regardless of which provider (Claude/Codex) is running inside the container.

The wrappers use a **thin shell script + Python evaluator** architecture. Each tool gets a small shell wrapper (~10 lines) that delegates to a single `scc-safety-eval` Python CLI script. The evaluator embeds the safety logic from S01's core modules (shell tokenizer, git safety rules, network tool rules, safety engine) as a standalone bundle with no external dependencies beyond Python 3 stdlib. Policy is read from `$SCC_POLICY_PATH`; when missing, the evaluator defaults to block mode (fail-closed per D009/spec-05).

S02 does NOT integrate policy mounting into the OCI adapter launch flow — that's S04 scope (fail-closed policy loading). The wrappers are functional and testable on their own: without policy, they block; with policy, they evaluate. Integration wiring happens downstream.

## Recommendation

Use the **shell wrapper + standalone Python evaluator** approach:

1. Create a self-contained Python evaluator package at `images/scc-base/wrappers/scc_safety_eval/` that embeds the core safety logic from S01. The modules (`shell_tokenizer.py`, `git_safety_rules.py`, `network_tool_rules.py`, `safety_engine.py`, `contracts.py`, `enums.py`) are all pure stdlib Python — copy them into the evaluator package and add a CLI entry point.

2. Create shell wrapper scripts for each tool (git, curl, wget, ssh, scp, sftp, rsync) at `images/scc-base/wrappers/bin/`. Each wrapper calls the evaluator, then either blocks or exec's the real binary at its absolute path.

3. Update `images/scc-base/Dockerfile` to install `python3`, COPY the evaluator and wrappers, and prepend the wrapper bin to PATH.

4. Add contract tests that verify the evaluator produces the same verdicts as `DefaultSafetyEngine` for the same inputs. This is the behavioral equivalence proof.

Why this over alternatives:
- **Pure-bash wrappers** would reimplement git argument parsing in bash — fragile and would diverge from the tested core logic.
- **Embedding scc-cli pip package** in the base image is too heavy and couples the image to the full CLI distribution.
- **Self-contained evaluator** reuses battle-tested logic, adds only python3 to the image, and is independently testable outside Docker.

## Implementation Landscape

### Key Files

- `src/scc_cli/core/safety_engine.py` — The `DefaultSafetyEngine` orchestrator from S01. The evaluator's logic must produce identical verdicts.
- `src/scc_cli/core/shell_tokenizer.py` — Pure-stdlib tokenizer (5 public functions). Will be copied into the evaluator package.
- `src/scc_cli/core/git_safety_rules.py` — All git safety analyzers. ~520 lines, pure functions. Will be copied into the evaluator package.
- `src/scc_cli/core/network_tool_rules.py` — Network tool detection for 6 tools. ~55 lines. Will be copied into the evaluator package.
- `src/scc_cli/core/contracts.py` — `SafetyPolicy`, `SafetyVerdict` dataclasses. Only these two are needed by the evaluator.
- `src/scc_cli/core/enums.py` — `CommandFamily` enum. Only this one enum is needed.
- `images/scc-base/Dockerfile` — Currently installs git, curl, ca-certificates, jq. Needs python3 added, wrappers COPY'd, PATH updated.
- `images/scc-base/wrappers/` — New directory. Contains the evaluator package and shell wrapper scripts.
- `tests/fakes/fake_safety_engine.py` — Existing fake for downstream tests.
- `src/scc_cli/docker/launch.py` — Has `SCC_POLICY_PATH` and policy mounting for Docker Desktop path. Reference for how policy gets into containers (S04 will wire the OCI path).

### Evaluator Package Layout

```
images/scc-base/wrappers/
  scc_safety_eval/
    __init__.py           # Package marker
    __main__.py           # CLI entry point: python3 -m scc_safety_eval <tool> <args>
    engine.py             # DefaultSafetyEngine equivalent (orchestration)
    shell_tokenizer.py    # Copied from core/shell_tokenizer.py
    git_safety_rules.py   # Copied from core/git_safety_rules.py
    network_tool_rules.py # Copied from core/network_tool_rules.py
    contracts.py          # SafetyPolicy + SafetyVerdict only
    enums.py              # CommandFamily only
    policy.py             # Policy loading from SCC_POLICY_PATH with fail-closed defaults
  bin/
    git                   # Shell wrapper
    curl                  # Shell wrapper
    wget                  # Shell wrapper
    ssh                   # Shell wrapper
    scp                   # Shell wrapper
    sftp                  # Shell wrapper
    rsync                 # Shell wrapper
```

### Shell Wrapper Shape

Each wrapper follows the same pattern:

```bash
#!/bin/bash
set -euo pipefail
REAL_BIN=/usr/bin/<tool>
EVAL_DIR=/usr/local/lib/scc
verdict=$(python3 -m scc_safety_eval "$0" "$@" 2>&1) || {
  rc=$?
  if [ "$rc" -eq 2 ]; then
    echo "$verdict" >&2
    exit 2
  fi
}
exec "$REAL_BIN" "$@"
```

Key details:
- `$0` gives the wrapper's own name (e.g., `git`), identifying the tool.
- Exit code 2 = block (matches existing plugin hook contract).
- Exit code 0 = allow, falls through to exec the real binary.
- `exec` replaces the wrapper process with the real binary — no overhead after evaluation.
- Real binary paths are absolute (`/usr/bin/git`, `/usr/bin/curl`) to avoid wrapper self-recursion.

### Evaluator CLI Contract

```
Usage: python3 -m scc_safety_eval <tool> [args...]

Environment:
  SCC_POLICY_PATH  — path to policy JSON file (optional, fail-closed if missing)

Exit codes:
  0  — command allowed
  2  — command blocked (reason on stderr)

Policy JSON shape (same as SafetyPolicy):
  {"action": "block"|"warn"|"allow", "rules": {"block_force_push": true, ...}}
```

### Dockerfile Changes

```dockerfile
# Add python3 for safety evaluator
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git curl ca-certificates jq python3 \
    && rm -rf /var/lib/apt/lists/*

# Install SCC safety wrappers
COPY wrappers/scc_safety_eval/ /usr/local/lib/scc/scc_safety_eval/
COPY wrappers/bin/ /usr/local/lib/scc/bin/
RUN chmod +x /usr/local/lib/scc/bin/*

# Prepend wrapper bin to PATH so wrappers shadow real binaries
ENV PATH="/usr/local/lib/scc/bin:$PATH"
```

### Build Order

1. **T01 — Standalone evaluator package + policy loader.** Create `images/scc-base/wrappers/scc_safety_eval/` with the engine, rule modules, policy loader, and CLI entry point. This is the riskiest part — it must produce identical verdicts to `DefaultSafetyEngine`. Write unit tests for the evaluator that mirror `tests/test_safety_engine.py`. Add a contract test that feeds identical inputs to both `DefaultSafetyEngine` and the evaluator CLI and asserts identical verdicts.

2. **T02 — Shell wrappers + Dockerfile.** Create the 7 shell wrapper scripts in `images/scc-base/wrappers/bin/`. Update `images/scc-base/Dockerfile` to install python3, COPY wrappers, and set PATH. Write tests for each wrapper that verify: blocked commands return exit 2, allowed commands pass through, missing policy defaults to block.

3. **T03 — Integration tests + boundary guardrails.** Verify the full chain: wrapper → evaluator → verdict for all command families. Add a boundary guardrail test that ensures the evaluator's core modules stay in sync with `src/scc_cli/core/` (hash comparison or AST diff). Confirm all existing tests still pass.

### Verification Approach

```bash
# Unit tests for evaluator
uv run pytest tests/test_safety_eval_standalone.py -v

# Contract tests: evaluator vs DefaultSafetyEngine equivalence
uv run pytest tests/test_safety_eval_contract.py -v

# Wrapper behavior tests (no Docker needed)
uv run pytest tests/test_runtime_wrappers.py -v

# Boundary guardrail: evaluator modules in sync with core
uv run pytest tests/test_safety_eval_sync.py -v

# Full suite regression
uv run mypy src/scc_cli
uv run ruff check
uv run pytest --rootdir "$PWD" -q
```

## Constraints

- **Ubuntu 22.04 base image does not include python3 by default.** The `ubuntu:22.04` Docker image is minimal. `python3` must be added to the `apt-get install` line. This adds ~30MB to the image but is the only way to reuse the safety logic without reimplementing it in bash.
- **Images are design-only (no build/push pipeline).** Per KNOWLEDGE.md, `images/` from M003 has no CI. The Dockerfile is a design artifact; tests verify the evaluator logic without Docker. A sync guardrail test catches drift between the evaluator modules and core.
- **The OCI adapter does not mount safety policy into containers yet.** The Docker Desktop path (`docker/launch.py`) sets `SCC_POLICY_PATH` and mounts policy. The OCI adapter (`adapters/oci_sandbox_runtime.py`) does not. S02's wrappers handle this correctly by defaulting to block (fail-closed). S04 will wire policy mounting.
- **Wrapper scope is exactly 7 tools: git, curl, wget, ssh, scp, sftp, rsync.** No package managers, cloud CLIs, or other command families per the active override.

## Common Pitfalls

- **Wrapper self-recursion.** If a wrapper is on PATH and calls the tool by name (e.g., `git` instead of `/usr/bin/git`), it calls itself infinitely. Each wrapper must use the absolute path to the real binary.
- **Evaluator module drift.** The evaluator's safety modules are copies of `src/scc_cli/core/`. If core changes, the evaluator goes stale. The sync guardrail test (`test_safety_eval_sync.py`) should hash both versions and fail if they diverge. This makes drift visible, not silent.
- **Policy path variations.** The Docker Desktop path uses `SCC_POLICY_PATH` pointing to a mounted file. The OCI path doesn't set this yet. The evaluator must handle: env var set and file exists (read policy), env var set but file missing (fail-closed block), env var not set (fail-closed block). Never fail-open.
- **Python startup overhead.** Each wrapper invocation starts a Python interpreter. For git in particular, subcommands like `git status` may be called frequently. The evaluator should be lightweight — import only the needed modules, no heavy initialization. The overhead is ~50-100ms per call, acceptable for safety-critical interception.

## Open Risks

- **The evaluator-to-core sync problem becomes real when images are built in CI.** For now, the sync guardrail test catches drift at development time. A future CI pipeline should generate the evaluator from core sources rather than maintaining copies. This is not S02 scope but should be noted for M005 or the image distribution strategy.
