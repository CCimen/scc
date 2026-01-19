"""Session selection use case for launch flows."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from scc_cli.application.interaction_requests import SelectOption, SelectRequest
from scc_cli.application.sessions import SessionService
from scc_cli.ports.session_models import SessionFilter, SessionSummary


class SessionSelectionMode(str, Enum):
    """Selection modes for session retrieval."""

    SELECT = "select"
    RESUME = "resume"


@dataclass(frozen=True)
class SelectSessionDependencies:
    """Dependencies for the SelectSession use case.

    Invariants:
        - Session service must provide stable ordering of recent sessions.

    Args:
        session_service: SessionService for loading session summaries.
    """

    session_service: SessionService


@dataclass(frozen=True)
class SelectSessionRequest:
    """Inputs for selecting or resuming a session.

    Invariants:
        - Selection uses the same filtering rules as existing CLI flows.

    Args:
        mode: Selection mode (select vs resume).
        team: Optional team filter.
        include_all: Whether to include sessions from all teams.
        limit: Max sessions to load.
        selection: Selected item from a prior prompt.
    """

    mode: SessionSelectionMode
    team: str | None
    include_all: bool
    limit: int
    selection: SessionSelectionItem | None = None


@dataclass(frozen=True)
class SessionSelectionItem:
    """Selectable session item for prompts.

    Invariants:
        - item_id remains stable for UI adapters.

    Args:
        item_id: Stable identifier for the item.
        summary: Session summary payload.
    """

    item_id: str
    summary: SessionSummary


@dataclass(frozen=True)
class SessionSelectionPrompt:
    """Prompt metadata returned to UI layers.

    Invariants:
        - Request metadata stays stable for UI adapters.

    Args:
        request: Selection request describing session options.
    """

    request: SelectRequest[SessionSelectionItem]


@dataclass(frozen=True)
class SessionSelectionWarning:
    """Warning details returned when selection is unavailable.

    Invariants:
        - Titles and messages remain stable for characterization tests.

    Args:
        title: Warning title for rendering.
        message: Warning message.
        suggestion: Optional suggestion for next steps.
    """

    title: str
    message: str
    suggestion: str | None = None


@dataclass(frozen=True)
class SessionSelectionWarningOutcome:
    """Warning outcome returned to the command/UI edge.

    Args:
        warning: Warning metadata to render.
    """

    warning: SessionSelectionWarning


@dataclass(frozen=True)
class SelectSessionResult:
    """Selected session result for launch flows.

    Invariants:
        - Selected session summary must match a stored session record.

    Args:
        session: Selected session summary.
    """

    session: SessionSummary


SessionSelectionOutcome = (
    SessionSelectionPrompt | SessionSelectionWarningOutcome | SelectSessionResult
)


def select_session(
    request: SelectSessionRequest,
    *,
    dependencies: SelectSessionDependencies,
) -> SessionSelectionOutcome:
    """Select or resume a session without performing UI prompts.

    Invariants:
        - Session ordering mirrors the persistence layer ordering.
        - Empty session lists return warnings instead of raising.

    Args:
        request: Selection inputs and optional resolved selection.
        dependencies: Use case dependencies.

    Returns:
        Session selection prompt, warning, or selected session result.
    """
    if request.selection is not None:
        return SelectSessionResult(session=request.selection.summary)

    summaries = _load_recent_sessions(request, dependencies.session_service)
    if not summaries:
        return SessionSelectionWarningOutcome(
            SessionSelectionWarning(
                title="No Recent Sessions",
                message="No recent sessions found.",
            )
        )

    if request.mode is SessionSelectionMode.RESUME:
        return SelectSessionResult(session=summaries[0])

    return SessionSelectionPrompt(request=_build_select_request(summaries))


def _load_recent_sessions(
    request: SelectSessionRequest,
    session_service: SessionService,
) -> list[SessionSummary]:
    session_filter = SessionFilter(
        limit=request.limit,
        team=request.team,
        include_all=request.include_all,
    )
    result = session_service.list_recent(session_filter)
    return result.sessions


def _build_select_request(summaries: list[SessionSummary]) -> SelectRequest[SessionSelectionItem]:
    options = []
    for index, summary in enumerate(summaries, start=1):
        item = SessionSelectionItem(item_id=f"session:{index}", summary=summary)
        options.append(
            SelectOption(
                option_id=item.item_id,
                label=summary.name,
                description=summary.workspace,
                value=item,
            )
        )
    return SelectRequest(
        request_id="select-session",
        title="Select Session",
        subtitle="Recent sessions",
        options=options,
        allow_back=False,
    )
