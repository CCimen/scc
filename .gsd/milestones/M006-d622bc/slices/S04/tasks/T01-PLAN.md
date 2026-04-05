---
estimated_steps: 28
estimated_files: 8
skills_used: []
---

# T01: Add provider_id to session models and thread through record/list

## Description

Add `provider_id: str | None = None` to SessionRecord, SessionSummary, and SessionFilter. Thread it through record_session, list_recent, _record_session_and_context, and all call sites in the launch flow. This is foundational — T02 and T04 depend on sessions carrying provider_id.

## Steps

1. Read `src/scc_cli/ports/session_models.py`. Add `provider_id: str | None = None` field to SessionRecord (after schema_version), SessionSummary (after branch), and SessionFilter (after include_all). Update `from_dict()` on SessionRecord to extract provider_id with default None. Bump `schema_version` default to 2 on SessionRecord.
2. Read `src/scc_cli/application/sessions/use_cases.py`. Thread `provider_id` through `record_session()` method — pass it to the SessionRecord constructor. Thread `provider_id` through filtering in list_recent: if `SessionFilter.provider_id` is set, filter sessions where `provider_id` matches.
3. Read `src/scc_cli/sessions.py`. Add `provider_id: str | None = None` parameter to `record_session()` and `list_recent()`. Pass through to service calls.
4. Read `src/scc_cli/commands/launch/flow_session.py`. Add `provider_id: str | None = None` parameter to `_record_session_and_context()`. Pass to `sessions.record_session()`.
5. Read `src/scc_cli/commands/launch/flow.py` around line 368 where `_record_session_and_context` is called. Thread `resolved_provider` (already in scope) as `provider_id=resolved_provider`.
6. Read `src/scc_cli/commands/launch/flow_interactive.py` around line 708 where `_record_session_and_context` is called. Thread the resolved provider_id (find it in scope from the interactive flow).
7. Read `src/scc_cli/commands/launch/sandbox.py` around line 97 where `sessions.record_session()` is called. Thread provider_id if available in scope, or pass None.
8. Create `tests/test_session_provider_id.py` with tests:
   - SessionRecord round-trip with provider_id set and None
   - SessionRecord.from_dict() with and without provider_id key (backward compat)
   - SessionSummary with provider_id field
   - SessionFilter with provider_id filtering
   - schema_version defaults to 2 for new records

## Must-Haves

- [ ] SessionRecord, SessionSummary, SessionFilter all have `provider_id: str | None = None`
- [ ] SessionRecord.from_dict() handles missing provider_id gracefully
- [ ] record_session() accepts and stores provider_id
- [ ] _record_session_and_context() passes provider_id through
- [ ] flow.py and flow_interactive.py thread resolved_provider to session recording
- [ ] All new code passes ruff, mypy

## Verification

- `uv run pytest tests/test_session_provider_id.py -v --no-cov` — all tests pass
- `uv run ruff check src/scc_cli/ports/session_models.py src/scc_cli/sessions.py src/scc_cli/commands/launch/flow_session.py` — clean
- `uv run mypy src/scc_cli/ports/session_models.py src/scc_cli/sessions.py src/scc_cli/commands/launch/flow_session.py` — no issues
- `uv run pytest --rootdir "$PWD" -q --no-cov` — zero regressions

## Inputs

- ``src/scc_cli/ports/session_models.py` — SessionRecord, SessionSummary, SessionFilter dataclasses`
- ``src/scc_cli/application/sessions/use_cases.py` — SessionService with record_session and list_recent`
- ``src/scc_cli/sessions.py` — facade module for session operations`
- ``src/scc_cli/commands/launch/flow_session.py` — _record_session_and_context helper`
- ``src/scc_cli/commands/launch/flow.py` — start() launch flow with resolved_provider in scope`
- ``src/scc_cli/commands/launch/flow_interactive.py` — interactive flow calling _record_session_and_context`
- ``src/scc_cli/commands/launch/sandbox.py` — sandbox launch calling sessions.record_session`

## Expected Output

- ``src/scc_cli/ports/session_models.py` — provider_id on SessionRecord, SessionSummary, SessionFilter`
- ``src/scc_cli/application/sessions/use_cases.py` — provider_id threading in record and filter`
- ``src/scc_cli/sessions.py` — provider_id param on record_session and list_recent`
- ``src/scc_cli/commands/launch/flow_session.py` — provider_id param on _record_session_and_context`
- ``src/scc_cli/commands/launch/flow.py` — resolved_provider threaded to session recording`
- ``src/scc_cli/commands/launch/flow_interactive.py` — provider_id threaded to session recording`
- ``tests/test_session_provider_id.py` — session model and filtering tests`

## Verification

uv run pytest tests/test_session_provider_id.py -v --no-cov && uv run ruff check src/scc_cli/ports/session_models.py src/scc_cli/sessions.py src/scc_cli/commands/launch/flow_session.py && uv run mypy src/scc_cli/ports/session_models.py src/scc_cli/sessions.py src/scc_cli/commands/launch/flow_session.py && uv run pytest --rootdir "$PWD" -q --no-cov
