"""Interaction request models for use case/UI boundaries."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

BACK_ACTION_ID = "back"
BACK_ACTION_LABEL = "Back"
BACK_ACTION_HOTKEY = "esc"

CONFIRM_ACTION_ID = "confirm"
CONFIRM_ACTION_LABEL = "Yes"
CONFIRM_ACTION_HOTKEY = "y"

CANCEL_ACTION_ID = "cancel"
CANCEL_ACTION_LABEL = "No"
CANCEL_ACTION_HOTKEY = "n"

T = TypeVar("T")


@dataclass(frozen=True)
class SelectOption(Generic[T]):
    """Selectable option for a SelectRequest.

    Invariants:
        - `option_id`, `label`, and `hotkey` remain stable for adapters.

    Args:
        option_id: Stable identifier for the option.
        label: Display label for UI adapters.
        hotkey: Optional hotkey label shown to users.
        description: Optional helper text for the option.
        value: Optional payload returned when selected.
    """

    option_id: str
    label: str
    hotkey: str | None = None
    description: str | None = None
    value: T | None = None


@dataclass(frozen=True)
class ConfirmRequest:
    """Request a yes/no confirmation at the UI edge.

    Invariants:
        - Confirm/cancel/back identifiers, labels, and hotkeys stay stable.

    Args:
        request_id: Stable identifier for the confirmation request.
        prompt: Prompt text for the confirmation.
        confirm_id: Stable identifier for the confirm action.
        confirm_label: Display label for the confirm action.
        confirm_hotkey: Hotkey label for the confirm action.
        cancel_id: Stable identifier for the cancel action.
        cancel_label: Display label for the cancel action.
        cancel_hotkey: Hotkey label for the cancel action.
        allow_back: Whether the UI may return the back action.
        back_id: Stable identifier for the back action.
        back_label: Display label for the back action.
        back_hotkey: Hotkey label for the back action.
    """

    request_id: str
    prompt: str
    confirm_id: str = CONFIRM_ACTION_ID
    confirm_label: str = CONFIRM_ACTION_LABEL
    confirm_hotkey: str = CONFIRM_ACTION_HOTKEY
    cancel_id: str = CANCEL_ACTION_ID
    cancel_label: str = CANCEL_ACTION_LABEL
    cancel_hotkey: str = CANCEL_ACTION_HOTKEY
    allow_back: bool = False
    back_id: str = BACK_ACTION_ID
    back_label: str = BACK_ACTION_LABEL
    back_hotkey: str = BACK_ACTION_HOTKEY


@dataclass(frozen=True)
class SelectRequest(Generic[T]):
    """Request that the user selects from a list of options.

    Invariants:
        - Option identifiers, labels, and hotkeys stay stable.
        - Back action metadata stays stable when enabled.

    Args:
        request_id: Stable identifier for the selection request.
        title: Title displayed above the selection list.
        options: Sequence of selection options.
        subtitle: Optional subtitle for context.
        allow_back: Whether the UI may return the back action.
        back_id: Stable identifier for the back action.
        back_label: Display label for the back action.
        back_hotkey: Hotkey label for the back action.
    """

    request_id: str
    title: str
    options: Sequence[SelectOption[T]]
    subtitle: str | None = None
    allow_back: bool = False
    back_id: str = BACK_ACTION_ID
    back_label: str = BACK_ACTION_LABEL
    back_hotkey: str = BACK_ACTION_HOTKEY


@dataclass(frozen=True)
class InputRequest:
    """Request text input from the user.

    Invariants:
        - Back action metadata stays stable when enabled.

    Args:
        request_id: Stable identifier for the input request.
        prompt: Prompt text for the input.
        default: Optional default value.
        placeholder: Optional placeholder for UI adapters.
        allow_back: Whether the UI may return the back action.
        back_id: Stable identifier for the back action.
        back_label: Display label for the back action.
        back_hotkey: Hotkey label for the back action.
    """

    request_id: str
    prompt: str
    default: str | None = None
    placeholder: str | None = None
    allow_back: bool = False
    back_id: str = BACK_ACTION_ID
    back_label: str = BACK_ACTION_LABEL
    back_hotkey: str = BACK_ACTION_HOTKEY


InteractionRequest = ConfirmRequest | SelectRequest[object] | InputRequest
