"""Unit tests for the select_session use case."""

from contextlib import AbstractContextManager, nullcontext

from scc_cli.application.launch import (
    SelectSessionDependencies,
    SelectSessionRequest,
    SelectSessionResult,
    SessionSelectionMode,
    SessionSelectionPrompt,
    SessionSelectionWarningOutcome,
    select_session,
)
from scc_cli.application.sessions import SessionService
from scc_cli.ports.session_models import SessionRecord


class FakeSessionStore:
    """In-memory SessionStore for select_session tests."""

    def __init__(self, sessions_list: list[SessionRecord] | None = None) -> None:
        self._sessions = list(sessions_list or [])

    def lock(self) -> AbstractContextManager[None]:
        return nullcontext()

    def load_sessions(self) -> list[SessionRecord]:
        return list(self._sessions)

    def save_sessions(self, sessions_list: list[SessionRecord]) -> None:
        self._sessions = list(sessions_list)


def _build_service(records: list[SessionRecord]) -> SessionService:
    return SessionService(FakeSessionStore(records))


def test_select_session_returns_prompt_for_select_mode() -> None:
    records = [
        SessionRecord(
            workspace="/tmp/proj-a",
            team="platform",
            last_used="2024-01-02T00:00:00",
        ),
        SessionRecord(
            workspace="/tmp/proj-b",
            team="platform",
            last_used="2024-01-03T00:00:00",
        ),
    ]
    service = _build_service(records)
    deps = SelectSessionDependencies(session_service=service)

    outcome = select_session(
        SelectSessionRequest(
            mode=SessionSelectionMode.SELECT,
            team="platform",
            include_all=False,
            limit=10,
        ),
        dependencies=deps,
    )

    assert isinstance(outcome, SessionSelectionPrompt)
    assert outcome.request.title == "Select Session"
    assert len(outcome.request.options) == 2


def test_select_session_returns_most_recent_for_resume() -> None:
    records = [
        SessionRecord(
            workspace="/tmp/proj-a",
            team="platform",
            last_used="2024-01-02T00:00:00",
        ),
        SessionRecord(
            workspace="/tmp/proj-b",
            team="platform",
            last_used="2024-01-03T00:00:00",
        ),
    ]
    service = _build_service(records)
    deps = SelectSessionDependencies(session_service=service)

    outcome = select_session(
        SelectSessionRequest(
            mode=SessionSelectionMode.RESUME,
            team="platform",
            include_all=False,
            limit=10,
        ),
        dependencies=deps,
    )

    assert isinstance(outcome, SelectSessionResult)
    assert outcome.session.workspace == "/tmp/proj-b"


def test_select_session_warns_when_empty() -> None:
    service = _build_service([])
    deps = SelectSessionDependencies(session_service=service)

    outcome = select_session(
        SelectSessionRequest(
            mode=SessionSelectionMode.SELECT,
            team="platform",
            include_all=False,
            limit=10,
        ),
        dependencies=deps,
    )

    assert isinstance(outcome, SessionSelectionWarningOutcome)
    assert outcome.warning.title == "No Recent Sessions"


def test_select_session_returns_selection_when_provided() -> None:
    record = SessionRecord(
        workspace="/tmp/proj-a",
        team="platform",
        last_used="2024-01-02T00:00:00",
    )
    service = _build_service([record])
    deps = SelectSessionDependencies(session_service=service)

    first = select_session(
        SelectSessionRequest(
            mode=SessionSelectionMode.SELECT,
            team="platform",
            include_all=False,
            limit=10,
        ),
        dependencies=deps,
    )
    assert isinstance(first, SessionSelectionPrompt)

    item = first.request.options[0].value
    assert item is not None

    outcome = select_session(
        SelectSessionRequest(
            mode=SessionSelectionMode.SELECT,
            team="platform",
            include_all=False,
            limit=10,
            selection=item,
        ),
        dependencies=deps,
    )

    assert isinstance(outcome, SelectSessionResult)
    assert outcome.session.workspace == "/tmp/proj-a"
