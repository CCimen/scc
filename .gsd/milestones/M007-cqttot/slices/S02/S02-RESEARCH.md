# S02 Research — Session, resume, and machine-readable output provider hardening

## Summary

Straightforward provider-parameterization of session, audit, and resume paths. All target files are known, patterns established by S01 (registry lookup via `get_runtime_spec()`) apply directly. Session models (`SessionRecord`, `SessionSummary`, `SessionFilter`) already carry `provider_id` fields and have filtering support. The work is wiring provider awareness into the remaining Claude-hardcoded helpers and surfacing provider_id in CLI output.

## Recommendation

Apply S01's registry pattern to five files. No new types needed, no risky integration, no unfamiliar APIs.

## Implementation Landscape

### What exists

1. **`sessions.py`** — Two Claude-named functions:
   - `get_claude_sessions_dir()` → returns `Path.home() / AGENT_CONFIG_DIR` (hardcoded `.claude`)
   - `get_claude_recent_sessions()` → reads `sessions.json` from the Claude dir
   - Neither function has any callers in the codebase (confirmed via rg). Both are dead code that can be renamed and parameterized safely.

2. **`commands/audit.py`** — `get_claude_dir()` returns `Path.home() / AGENT_CONFIG_DIR`. Used only by `audit_plugins_cmd` to locate plugin manifests. Plugin audit is inherently Claude-specific (Claude plugin format), but the function name should be provider-parameterized to use the registry's `config_dir` field.

3. **`commands/launch/sandbox.py`** — Legacy sandbox path records `provider_id=None` on line 102. The legacy sandbox path is always Claude — should record `provider_id='claude'` explicitly.

4. **Session models** — `SessionRecord`, `SessionSummary`, `SessionFilter` all already have `provider_id` fields. `SessionService.list_recent()` already threads `provider_id` through to summaries. `_filter_sessions()` already filters by `provider_id`. 12 existing tests in `test_session_provider_id.py` cover round-trip, filtering, and defaults.

5. **`commands/worktree/session_commands.py`** — Session list CLI (`sessions_cmd`):
   - `session_dicts` comprehension omits `provider_id` (line 85-95)
   - Table rows omit provider column (line 130-141)
   - `render_responsive_table` call has no provider column (line 152-163)

6. **`contexts.py` / `WorkContext`** — No `provider_id` field. Quick Resume contexts show `display_label` = "team · repo · branch". The `_build_quick_resume_options` function in `start_wizard.py` builds options from `WorkContext` without provider info.

7. **Audit reader** (`application/launch/audit_log.py`) — Already reads `provider_id` from JSONL metadata and populates `LaunchAuditEventRecord.provider_id`. Falls back to `subject` field when `provider_id` is absent. No changes needed here.

8. **`flow_session.py`** — `_record_session_and_context` already accepts `provider_id` parameter and passes it to `sessions.record_session()`. The OCI launch path in `flow.py` already passes `resolved_provider`.

9. **Provider registry** — `core/provider_registry.py` has `PROVIDER_REGISTRY` dict with `config_dir` field per provider. `get_runtime_spec()` provides fail-closed lookup.

### Natural seams

The work divides into three independent units:

**T01 — Rename Claude-hardcoded helpers and parameterize paths.** Touch `sessions.py` (rename + parameterize `get_claude_sessions_dir` and `get_claude_recent_sessions`), `commands/audit.py` (rename `get_claude_dir` to use registry lookup), `commands/launch/sandbox.py` (change `provider_id=None` to `provider_id='claude'`). These are independent edits with no cross-dependencies.

**T02 — Add provider_id to session list CLI and Quick Resume.** Touch `commands/worktree/session_commands.py` (add `provider_id` to session_dicts and table columns), `contexts.py` (add `provider_id` field to `WorkContext` with backward compat). Touch Quick Resume display label or description to include provider info.

**T03 — Tests and verification.** Add tests for the renamed helpers, verify provider column in session list output, test WorkContext round-trip with provider_id.

### Constraints

- `get_claude_sessions_dir()` and `get_claude_recent_sessions()` have zero callers — renaming is safe with no downstream impact.
- `get_claude_dir()` in `commands/audit.py` is called only by `audit_plugins_cmd`. Plugin audit is Claude-specific but the path lookup should use the registry.
- `WorkContext.from_dict()` must handle backward compatibility — old contexts without `provider_id` should default to `None`.
- The `render_responsive_table` pattern uses `wide_columns` for extra columns shown on wide terminals. Provider column fits naturally as a wide column.
- Session list JSON output (`build_session_list_data`) already accepts `provider_id` param — just needs to be populated from session data.

### What to verify

1. `uv run pytest tests/test_session_provider_id.py tests/test_sessions.py tests/test_audit_cli.py tests/test_contexts.py -v` — existing tests still pass after renames
2. `uv run ruff check` on all touched files
3. `uv run mypy` on all touched files
4. `uv run pytest -q` — full suite, zero regressions
5. New tests confirm: renamed helpers work with provider_id parameter, sandbox records `provider_id='claude'`, session list includes provider column, WorkContext round-trips provider_id
