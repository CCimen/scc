"""Key mapping and input handling for interactive UI.

This module provides the input layer for the interactive UI system,
translating raw keyboard input (via readchar) into semantic Action
objects that ListScreen and other components can process.

Features:
- Cross-platform key reading via readchar
- Vim-style navigation (j/k) in addition to arrow keys
- Customizable key maps for different list modes
- Type-to-filter support for printable characters

Example:
    >>> key = read_key()
    >>> action = map_key_to_action(key, mode=ListMode.SINGLE_SELECT)
    >>> if action.action_type == ActionType.SELECT:
    ...     return action.result
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, Generic, TypeVar

import readchar

if TYPE_CHECKING:
    pass

T = TypeVar("T")


class TeamSwitchRequested(Exception):  # noqa: N818
    """Raised when user presses 't' to switch teams.

    This exception allows interactive components to signal that the user wants to
    switch teams without selecting an item. The caller should catch this and
    redirect to team selection.

    Note: Named without 'Error' suffix because this is a control flow signal
    (like StopIteration), not an error condition.
    """

    pass


class StartRequested(Exception):  # noqa: N818
    """Raised when user wants to start a new session from dashboard.

    This is a control flow signal (like TeamSwitchRequested) that allows
    the dashboard to request the start wizard without coupling to CLI logic.

    The orchestrator (run_dashboard) catches this and runs the start flow.

    Attributes:
        return_to: Tab name to restore after flow (e.g., "CONTAINERS").
            Uses enum .name (stable identifier), not .value (display string).
        reason: Context for logging/toast (e.g., "no_containers").
    """

    def __init__(self, return_to: str = "", reason: str = "") -> None:
        self.return_to = return_to
        self.reason = reason
        super().__init__(reason)


class RefreshRequested(Exception):  # noqa: N818
    """Raised when user requests data refresh via 'r' key.

    This is a control flow signal that allows the dashboard to request
    a data reload without directly calling data loading functions.

    The orchestrator catches this and reloads tab data.

    Attributes:
        return_to: Tab name to restore after refresh.
    """

    def __init__(self, return_to: str = "") -> None:
        self.return_to = return_to
        super().__init__()


class ActionType(Enum):
    """Types of actions that can result from key handling.

    Actions are semantic representations of user intent, abstracted
    from the specific keys used to trigger them.
    """

    NAVIGATE_UP = auto()
    NAVIGATE_DOWN = auto()
    SELECT = auto()  # Enter in single-select
    TOGGLE = auto()  # Space in multi-select
    TOGGLE_ALL = auto()  # 'a' in multi-select
    CONFIRM = auto()  # Enter in multi-select
    CANCEL = auto()  # Esc
    QUIT = auto()  # 'q'
    HELP = auto()  # '?'
    FILTER_CHAR = auto()  # Printable character for filtering
    FILTER_DELETE = auto()  # Backspace
    TAB_NEXT = auto()  # Tab
    TAB_PREV = auto()  # Shift+Tab
    TEAM_SWITCH = auto()  # 't' - switch to team selection
    REFRESH = auto()  # 'r' - reload data
    CUSTOM = auto()  # Action key defined by caller


@dataclass
class Action(Generic[T]):
    """Result of handling a key press.

    Attributes:
        action_type: The semantic action type.
        should_exit: Whether the event loop should terminate.
        result: Optional result value (for SELECT, CONFIRM actions).
        state_changed: Whether the UI needs to re-render.
        custom_key: The key pressed, for CUSTOM action type.
        filter_char: The character to add to filter, for FILTER_CHAR type.
    """

    action_type: ActionType
    should_exit: bool = False
    result: T | None = None
    state_changed: bool = True
    custom_key: str | None = None
    filter_char: str | None = None


# Default key mappings for navigation and common actions.
# These are shared across all list modes.
# NOTE: Dashboard-specific keys like 'r' (refresh) should NOT be here.
# They are handled explicitly in the Dashboard component.
DEFAULT_KEY_MAP: dict[str, ActionType] = {
    # Arrow key navigation
    readchar.key.UP: ActionType.NAVIGATE_UP,
    readchar.key.DOWN: ActionType.NAVIGATE_DOWN,
    # Vim-style navigation
    "k": ActionType.NAVIGATE_UP,
    "j": ActionType.NAVIGATE_DOWN,
    # Selection and confirmation
    readchar.key.ENTER: ActionType.SELECT,
    readchar.key.SPACE: ActionType.TOGGLE,
    "a": ActionType.TOGGLE_ALL,
    # Cancel and quit
    readchar.key.ESC: ActionType.CANCEL,
    "q": ActionType.QUIT,
    # Help
    "?": ActionType.HELP,
    # Tab navigation
    readchar.key.TAB: ActionType.TAB_NEXT,
    readchar.key.SHIFT_TAB: ActionType.TAB_PREV,
    # Filter control
    readchar.key.BACKSPACE: ActionType.FILTER_DELETE,
    # Team switching
    "t": ActionType.TEAM_SWITCH,
}


def read_key() -> str:
    """Read a single key press from stdin.

    This function blocks until a key is pressed. It handles
    multi-byte escape sequences for special keys (arrows, etc.)
    via readchar.

    Returns:
        The key pressed as a string. Special keys are returned
        as readchar.key constants (e.g., readchar.key.UP).
    """
    return readchar.readkey()


def is_printable(key: str) -> bool:
    """Check if a key is a printable character for type-to-filter.

    Args:
        key: The key to check.

    Returns:
        True if the key is a single printable character that
        should be added to the filter query.
    """
    # Single character, printable ASCII (excluding control chars)
    if len(key) != 1:
        return False

    # Check if it's a printable character (space through tilde)
    # but exclude keys that have special meanings
    code = ord(key)
    if code < 32 or code > 126:  # noqa: PLR2004
        return False

    # Exclude keys with special bindings
    # (they'll be handled by the key map first)
    # NOTE: 'r' is NOT here - it's a filterable char. Dashboard handles 'r' explicitly.
    special_keys = {"q", "?", "a", "j", "k", " ", "t"}
    return key not in special_keys


def map_key_to_action(
    key: str,
    *,
    custom_keys: dict[str, str] | None = None,
    enable_filter: bool = True,
    filter_active: bool = False,
) -> Action[None]:
    """Map a key press to a semantic action.

    The mapping process follows this priority:
    1. If filter_active and key is j/k, treat as FILTER_CHAR (user is typing)
    2. Check DEFAULT_KEY_MAP for standard actions
    3. Check custom_keys for caller-defined actions
    4. If enable_filter and printable, return FILTER_CHAR
    5. Otherwise, return no-op (state_changed=False)

    Args:
        key: The key that was pressed (from read_key()).
        custom_keys: Optional mapping of keys to custom action names.
        enable_filter: Whether to treat printable chars as filter input.
        filter_active: Whether a filter query is currently active. When True,
            j/k become filter characters instead of navigation shortcuts.

    Returns:
        An Action describing the semantic meaning of the key press.

    Example:
        >>> action = map_key_to_action(readchar.key.UP)
        >>> action.action_type
        ActionType.NAVIGATE_UP

        >>> action = map_key_to_action("s", custom_keys={"s": "shell"})
        >>> action.action_type
        ActionType.CUSTOM
        >>> action.custom_key
        's'
    """
    # Priority 1: When filter is active, certain mapped keys become filter characters
    # (user is typing, arrow keys still work for navigation)
    # j/k = vim navigation, t = team switch, a = toggle all - all filterable when typing
    if filter_active and enable_filter and key in ("j", "k", "t", "a"):
        return Action(
            action_type=ActionType.FILTER_CHAR,
            filter_char=key,
            should_exit=False,
        )

    # Priority 2: Check standard key map
    if key in DEFAULT_KEY_MAP:
        action_type = DEFAULT_KEY_MAP[key]
        should_exit = action_type in (
            ActionType.CANCEL,
            ActionType.QUIT,
            ActionType.SELECT,
        )
        return Action(action_type=action_type, should_exit=should_exit)

    # Priority 2: Check custom keys
    if custom_keys and key in custom_keys:
        return Action(
            action_type=ActionType.CUSTOM,
            custom_key=key,
            should_exit=False,
        )

    # Priority 3: Printable character for filter
    if enable_filter and is_printable(key):
        return Action(
            action_type=ActionType.FILTER_CHAR,
            filter_char=key,
            should_exit=False,
        )

    # No action - key not recognized
    return Action(action_type=ActionType.NAVIGATE_UP, state_changed=False)


class KeyReader:
    """High-level key reader with mode-aware action mapping.

    This class provides a convenient interface for reading and mapping
    keys in the context of a specific list mode.

    Attributes:
        custom_keys: Custom key bindings for ACTIONABLE mode.
        enable_filter: Whether type-to-filter is enabled.

    Example:
        >>> reader = KeyReader(custom_keys={"s": "shell", "l": "logs"})
        >>> action = reader.read()  # Blocks for input
        >>> if action.action_type == ActionType.CUSTOM:
        ...     handle_custom(action.custom_key)
    """

    def __init__(
        self,
        *,
        custom_keys: dict[str, str] | None = None,
        enable_filter: bool = True,
    ) -> None:
        """Initialize the key reader.

        Args:
            custom_keys: Custom key bindings mapping key → action name.
            enable_filter: Whether to enable type-to-filter behavior.
        """
        self.custom_keys = custom_keys or {}
        self.enable_filter = enable_filter

    def read(self, *, filter_active: bool = False) -> Action[None]:
        """Read a key and return the corresponding action.

        This method blocks until a key is pressed, then maps it
        to an Action using the configured settings.

        Args:
            filter_active: Whether a filter query is currently active.
                When True, j/k become filter characters instead of
                navigation shortcuts (arrow keys still work).

        Returns:
            The Action corresponding to the pressed key.
        """
        key = read_key()
        return map_key_to_action(
            key,
            custom_keys=self.custom_keys,
            enable_filter=self.enable_filter,
            filter_active=filter_active,
        )


# Re-export readchar.key for convenience
# This allows consumers to use keys.KEY_UP instead of importing readchar
KEY_UP = readchar.key.UP
KEY_DOWN = readchar.key.DOWN
KEY_ENTER = readchar.key.ENTER
KEY_SPACE = readchar.key.SPACE
KEY_ESC = readchar.key.ESC
KEY_TAB = readchar.key.TAB
KEY_BACKSPACE = readchar.key.BACKSPACE
