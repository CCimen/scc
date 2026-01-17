"""Tests for InteractionRequest schema stability."""

from __future__ import annotations

from scc_cli.application.interaction_requests import (
    BACK_ACTION_HOTKEY,
    BACK_ACTION_ID,
    BACK_ACTION_LABEL,
    CANCEL_ACTION_HOTKEY,
    CANCEL_ACTION_ID,
    CANCEL_ACTION_LABEL,
    CONFIRM_ACTION_HOTKEY,
    CONFIRM_ACTION_ID,
    CONFIRM_ACTION_LABEL,
    ConfirmRequest,
    InputRequest,
    SelectOption,
    SelectRequest,
)


def test_back_action_constants() -> None:
    """Back action metadata stays stable."""
    assert BACK_ACTION_ID == "back"
    assert BACK_ACTION_LABEL == "Back"
    assert BACK_ACTION_HOTKEY == "esc"


def test_confirm_request_defaults() -> None:
    """ConfirmRequest defaults preserve IDs, labels, and hotkeys."""
    request = ConfirmRequest(request_id="confirm-delete", prompt="Delete item?")

    assert request.confirm_id == CONFIRM_ACTION_ID
    assert request.confirm_label == CONFIRM_ACTION_LABEL
    assert request.confirm_hotkey == CONFIRM_ACTION_HOTKEY
    assert request.cancel_id == CANCEL_ACTION_ID
    assert request.cancel_label == CANCEL_ACTION_LABEL
    assert request.cancel_hotkey == CANCEL_ACTION_HOTKEY
    assert request.back_id == BACK_ACTION_ID
    assert request.back_label == BACK_ACTION_LABEL
    assert request.back_hotkey == BACK_ACTION_HOTKEY
    assert request.allow_back is False


def test_select_request_back_metadata() -> None:
    """SelectRequest retains back metadata when enabled."""
    option = SelectOption(option_id="alpha", label="Alpha", hotkey="a")
    request = SelectRequest(
        request_id="select-alpha",
        title="Pick",
        options=(option,),
        allow_back=True,
    )

    assert request.options[0].option_id == "alpha"
    assert request.options[0].label == "Alpha"
    assert request.options[0].hotkey == "a"
    assert request.allow_back is True
    assert request.back_id == BACK_ACTION_ID
    assert request.back_label == BACK_ACTION_LABEL
    assert request.back_hotkey == BACK_ACTION_HOTKEY


def test_input_request_back_metadata() -> None:
    """InputRequest retains back metadata when enabled."""
    request = InputRequest(request_id="input-name", prompt="Name", allow_back=True)

    assert request.allow_back is True
    assert request.back_id == BACK_ACTION_ID
    assert request.back_label == BACK_ACTION_LABEL
    assert request.back_hotkey == BACK_ACTION_HOTKEY
