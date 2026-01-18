from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum, auto
from typing import TypeAlias


class LaunchOutputKind(Enum):
    """Kinds of output events emitted by launch flows."""

    INFO = auto()
    WARNING = auto()
    SUCCESS = auto()


@dataclass(frozen=True)
class LaunchInfoEvent:
    """Informational output from the launch flow.

    Invariants:
        - message preserves existing launch messaging text.

    Args:
        message: Human-facing informational message.
    """

    message: str


@dataclass(frozen=True)
class LaunchWarningEvent:
    """Warning output from the launch flow.

    Invariants:
        - message preserves existing launch warning text.

    Args:
        message: Human-facing warning message.
    """

    message: str


@dataclass(frozen=True)
class LaunchSuccessEvent:
    """Success output from the launch flow.

    Invariants:
        - message preserves existing launch success text.

    Args:
        message: Human-facing success message.
    """

    message: str


LaunchOutputEvent: TypeAlias = LaunchInfoEvent | LaunchWarningEvent | LaunchSuccessEvent


@dataclass(frozen=True)
class LaunchOutputViewModel:
    """View model for launch output events.

    Invariants:
        - events remain ordered for deterministic rendering.

    Args:
        events: Ordered output events describing launch progress.
    """

    events: Sequence[LaunchOutputEvent]
