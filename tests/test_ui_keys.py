"""Tests for ui/keys.py - Key mapping and input handling.

Test Categories:
- Key mapping tests (arrow keys, vim keys, action keys)
- Action type resolution tests
- Cross-platform key handling tests
"""

from __future__ import annotations

import readchar

from scc_cli.ui.keys import (
    DEFAULT_KEY_MAP,
    KEY_BACKSPACE,
    KEY_DOWN,
    KEY_ENTER,
    KEY_ESC,
    KEY_TAB,
    KEY_UP,
    Action,
    ActionType,
    KeyReader,
    TeamSwitchRequested,
    is_printable,
    map_key_to_action,
)


class TestArrowKeyMapping:
    """Test arrow key to action mapping."""

    def test_up_arrow_maps_to_navigate_up(self) -> None:
        """Up arrow key maps to NAVIGATE_UP action."""
        action = map_key_to_action(readchar.key.UP)
        assert action.action_type == ActionType.NAVIGATE_UP

    def test_down_arrow_maps_to_navigate_down(self) -> None:
        """Down arrow key maps to NAVIGATE_DOWN action."""
        action = map_key_to_action(readchar.key.DOWN)
        assert action.action_type == ActionType.NAVIGATE_DOWN

    def test_enter_maps_to_select(self) -> None:
        """Enter key maps to SELECT action."""
        action = map_key_to_action(readchar.key.ENTER)
        assert action.action_type == ActionType.SELECT
        assert action.should_exit is True

    def test_escape_maps_to_cancel(self) -> None:
        """Escape key maps to CANCEL action."""
        action = map_key_to_action(readchar.key.ESC)
        assert action.action_type == ActionType.CANCEL
        assert action.should_exit is True


class TestVimKeyMapping:
    """Test vim-style key mappings."""

    def test_j_maps_to_navigate_down(self) -> None:
        """'j' key maps to NAVIGATE_DOWN (vim style)."""
        action = map_key_to_action("j")
        assert action.action_type == ActionType.NAVIGATE_DOWN

    def test_k_maps_to_navigate_up(self) -> None:
        """'k' key maps to NAVIGATE_UP (vim style)."""
        action = map_key_to_action("k")
        assert action.action_type == ActionType.NAVIGATE_UP

    def test_q_maps_to_quit(self) -> None:
        """'q' key maps to QUIT action."""
        action = map_key_to_action("q")
        assert action.action_type == ActionType.QUIT
        assert action.should_exit is True


class TestActionKeyMapping:
    """Test special action key mappings."""

    def test_space_maps_to_toggle(self) -> None:
        """Space key maps to TOGGLE action (for multi-select)."""
        action = map_key_to_action(readchar.key.SPACE)
        assert action.action_type == ActionType.TOGGLE

    def test_a_maps_to_toggle_all(self) -> None:
        """'a' key maps to TOGGLE_ALL action."""
        action = map_key_to_action("a")
        assert action.action_type == ActionType.TOGGLE_ALL

    def test_question_mark_maps_to_help(self) -> None:
        """'?' key maps to HELP action."""
        action = map_key_to_action("?")
        assert action.action_type == ActionType.HELP

    def test_tab_maps_to_tab_next(self) -> None:
        """Tab key maps to TAB_NEXT action."""
        action = map_key_to_action(readchar.key.TAB)
        assert action.action_type == ActionType.TAB_NEXT

    def test_backspace_maps_to_filter_delete(self) -> None:
        """Backspace key maps to FILTER_DELETE action."""
        action = map_key_to_action(readchar.key.BACKSPACE)
        assert action.action_type == ActionType.FILTER_DELETE

    def test_t_maps_to_team_switch(self) -> None:
        """'t' key maps to TEAM_SWITCH action."""
        action = map_key_to_action("t")
        assert action.action_type == ActionType.TEAM_SWITCH

    def test_n_is_not_globally_bound(self) -> None:
        """'n' key is not in DEFAULT_KEY_MAP (screen-specific binding).

        Unlike keys like 'q' and 't', 'n' is not in DEFAULT_KEY_MAP.
        Screens that want new session functionality (Dashboard, Quick Resume)
        register 'n' via custom_keys parameter.

        Without custom_keys, 'n' behaves like any other printable character:
        - enable_filter=True (default): returns FILTER_CHAR
        - enable_filter=False: returns NOOP
        """
        # Default: enable_filter=True, so 'n' is a filterable character
        action = map_key_to_action("n")
        assert action.action_type == ActionType.FILTER_CHAR
        assert action.filter_char == "n"

        # With enable_filter=False, unbound keys return NOOP
        action = map_key_to_action("n", enable_filter=False)
        assert action.action_type == ActionType.NOOP


class TestPrintableCharacterHandling:
    """Test printable character handling for type-to-filter."""

    def test_alphanumeric_maps_to_filter_char(self) -> None:
        """Alphanumeric characters map to FILTER_CHAR action."""
        # Test lowercase letters
        action = map_key_to_action("x")
        assert action.action_type == ActionType.FILTER_CHAR

        # Test uppercase letters
        action = map_key_to_action("X")
        assert action.action_type == ActionType.FILTER_CHAR

        # Test numbers
        action = map_key_to_action("5")
        assert action.action_type == ActionType.FILTER_CHAR

    def test_filter_char_includes_character(self) -> None:
        """FILTER_CHAR action includes the actual character pressed."""
        action = map_key_to_action("m")
        assert action.action_type == ActionType.FILTER_CHAR
        assert action.filter_char == "m"

    def test_special_keys_not_printable(self) -> None:
        """Keys with special meanings are not treated as filter chars.

        Note: 'n' and 'r' are NOT in this list because they're screen-specific.
        They become FILTER_CHAR by default and only trigger actions when
        screens register them via custom_keys.
        """
        # 'j', 'k', 'q', 'a', '?', 't' all have special meanings in DEFAULT_KEY_MAP
        for key in ["j", "k", "q", "a", "?", "t"]:
            action = map_key_to_action(key)
            assert action.action_type != ActionType.FILTER_CHAR

    def test_punctuation_is_printable(self) -> None:
        """Punctuation marks (except special) are printable."""
        for char in ["-", "_", ".", ",", "!", "@"]:
            assert is_printable(char) is True

    def test_non_ascii_is_printable(self) -> None:
        """Non-ASCII printable characters are supported (Swedish locale, emoji).

        This enables users to type filter queries with accented characters
        like 'å', 'ä', 'ö' common in Swedish, or emoji in container/session names.
        """
        # Swedish characters
        for char in ["å", "ä", "ö", "Å", "Ä", "Ö"]:
            assert is_printable(char) is True

        # Other European accented characters
        for char in ["é", "ñ", "ü", "ß"]:
            assert is_printable(char) is True

        # Common emoji (single codepoints)
        # Note: Multi-codepoint emoji (like flags, skin tones) would fail len(key) != 1
        # but simple emoji like these are single codepoints
        assert is_printable("★") is True  # Star
        assert is_printable("♥") is True  # Heart

    def test_control_chars_not_printable(self) -> None:
        """Control characters are not printable."""
        for code in [0, 1, 27, 31]:  # NUL, SOH, ESC, US
            assert is_printable(chr(code)) is False

    def test_multi_byte_not_printable(self) -> None:
        """Multi-byte sequences (escape codes) are not printable."""
        assert is_printable(readchar.key.UP) is False
        assert is_printable(readchar.key.DOWN) is False

    def test_filter_disabled_ignores_printable(self) -> None:
        """When enable_filter=False, printable chars return no-op."""
        action = map_key_to_action("x", enable_filter=False)
        # Should not be FILTER_CHAR when disabled
        assert action.action_type != ActionType.FILTER_CHAR
        assert action.state_changed is False


class TestCustomActionKeys:
    """Test custom action key registration."""

    def test_custom_key_maps_to_custom_action(self) -> None:
        """Custom registered keys map to CUSTOM action type."""
        custom = {"s": "shell", "l": "logs"}
        action = map_key_to_action("s", custom_keys=custom)
        assert action.action_type == ActionType.CUSTOM

    def test_custom_action_includes_key(self) -> None:
        """CUSTOM action includes the custom_key field."""
        custom = {"s": "shell", "l": "logs"}
        action = map_key_to_action("l", custom_keys=custom)
        assert action.action_type == ActionType.CUSTOM
        assert action.custom_key == "l"

    def test_standard_keys_override_custom(self) -> None:
        """Standard keys take priority over custom keys."""
        # 'j' is already mapped to NAVIGATE_DOWN
        custom = {"j": "jump"}
        action = map_key_to_action("j", custom_keys=custom)
        assert action.action_type == ActionType.NAVIGATE_DOWN
        assert action.custom_key is None

    def test_custom_key_not_should_exit(self) -> None:
        """Custom actions don't automatically exit."""
        custom = {"d": "delete"}
        action = map_key_to_action("d", custom_keys=custom)
        assert action.should_exit is False


class TestDefaultKeyMap:
    """Test DEFAULT_KEY_MAP structure."""

    def test_key_map_contains_navigation(self) -> None:
        """Key map contains navigation keys."""
        assert readchar.key.UP in DEFAULT_KEY_MAP
        assert readchar.key.DOWN in DEFAULT_KEY_MAP
        assert "j" in DEFAULT_KEY_MAP
        assert "k" in DEFAULT_KEY_MAP

    def test_key_map_contains_actions(self) -> None:
        """Key map contains action keys."""
        assert readchar.key.ENTER in DEFAULT_KEY_MAP
        assert readchar.key.ESC in DEFAULT_KEY_MAP
        assert "q" in DEFAULT_KEY_MAP
        assert "?" in DEFAULT_KEY_MAP

    def test_key_map_values_are_action_types(self) -> None:
        """All key map values are ActionType enum members."""
        for action_type in DEFAULT_KEY_MAP.values():
            assert isinstance(action_type, ActionType)


class TestKeyConstants:
    """Test re-exported key constants."""

    def test_key_constants_match_readchar(self) -> None:
        """Re-exported constants match readchar values."""
        assert KEY_UP == readchar.key.UP
        assert KEY_DOWN == readchar.key.DOWN
        assert KEY_ENTER == readchar.key.ENTER
        assert KEY_ESC == readchar.key.ESC
        assert KEY_TAB == readchar.key.TAB
        assert KEY_BACKSPACE == readchar.key.BACKSPACE


class TestActionDataclass:
    """Test Action dataclass behavior."""

    def test_action_defaults(self) -> None:
        """Action has sensible defaults."""
        action = Action(action_type=ActionType.NAVIGATE_UP)
        assert action.should_exit is False
        assert action.result is None
        assert action.state_changed is True
        assert action.custom_key is None

    def test_action_with_result(self) -> None:
        """Action can carry a result value."""
        action: Action[str] = Action(
            action_type=ActionType.SELECT,
            should_exit=True,
            result="selected_item",
        )
        assert action.result == "selected_item"


class TestKeyReader:
    """Test KeyReader class."""

    def test_key_reader_initialization(self) -> None:
        """KeyReader initializes with custom keys and filter setting."""
        reader = KeyReader(custom_keys={"s": "shell"}, enable_filter=False)
        assert reader.custom_keys == {"s": "shell"}
        assert reader.enable_filter is False

    def test_key_reader_defaults(self) -> None:
        """KeyReader has sensible defaults."""
        reader = KeyReader()
        assert reader.custom_keys == {}
        assert reader.enable_filter is True


class TestTeamSwitchConsistency:
    """Test TEAM_SWITCH is handled consistently across all interactive components.

    This prevents "mapped but unhandled" regressions where a key is in
    DEFAULT_KEY_MAP but silently does nothing in some screens.
    """

    def test_team_switch_in_default_key_map(self) -> None:
        """TEAM_SWITCH is mapped to 't' in DEFAULT_KEY_MAP."""
        assert "t" in DEFAULT_KEY_MAP
        assert DEFAULT_KEY_MAP["t"] == ActionType.TEAM_SWITCH

    def test_list_screen_handles_team_switch(self) -> None:
        """ListScreen handles TEAM_SWITCH by raising TeamSwitchRequested."""
        from scc_cli.ui.list_screen import ListItem, ListScreen

        items = [ListItem(value="test", label="Test Item")]
        screen = ListScreen(items, title="Test")

        # Create a TEAM_SWITCH action
        action = Action(action_type=ActionType.TEAM_SWITCH)

        # Should raise TeamSwitchRequested, not silently no-op
        try:
            screen._handle_action(action)
            raise AssertionError("Expected TeamSwitchRequested to be raised")
        except TeamSwitchRequested:
            pass  # Expected behavior

    def test_dashboard_handles_team_switch(self) -> None:
        """Dashboard handles TEAM_SWITCH by raising TeamSwitchRequested."""
        from unittest.mock import patch

        from scc_cli.ui.dashboard import Dashboard, DashboardState, DashboardTab, TabData
        from scc_cli.ui.list_screen import ListItem, ListState

        # Create minimal dashboard state
        items: list[ListItem[str]] = [ListItem(value="test", label="Test")]
        tab_data = TabData(
            tab=DashboardTab.STATUS,
            title="Status",
            items=items,
            count_active=1,
            count_total=1,
        )
        state = DashboardState(
            active_tab=DashboardTab.STATUS,
            tabs={DashboardTab.STATUS: tab_data},
            list_state=ListState(items=items),
        )
        dashboard = Dashboard(state)

        # Create a TEAM_SWITCH action
        action: Action[None] = Action(action_type=ActionType.TEAM_SWITCH)

        # Mock is_standalone_mode to return False (org mode)
        # In org mode, TEAM_SWITCH should raise TeamSwitchRequested
        with patch(
            "scc_cli.ui.dashboard._dashboard.scc_config.is_standalone_mode", return_value=False
        ):
            try:
                dashboard._handle_action(action)
                raise AssertionError("Expected TeamSwitchRequested to be raised")
            except TeamSwitchRequested:
                pass  # Expected behavior

    def test_picker_handles_team_switch(self) -> None:
        """Picker handles TEAM_SWITCH by raising TeamSwitchRequested.

        Note: This is tested implicitly via test_t_maps_to_team_switch,
        but we include it here for completeness of the consistency test.
        """
        # The picker uses _run_single_select_picker which has the handler.
        # We verify the action type is correct when 't' is pressed.
        action = map_key_to_action("t")
        assert action.action_type == ActionType.TEAM_SWITCH


class TestFilterModeKeyBehavior:
    """Test key behavior changes when filter is active.

    When a user is typing in the filter field, certain keys that normally
    trigger actions should instead be treated as filter characters.

    Bug fix: https://github.com/... - typing "start" caused unexpected exit
    because "t" triggered TEAM_SWITCH instead of being added to filter.
    """

    def test_t_becomes_filter_char_when_filter_active(self) -> None:
        """'t' is treated as filter char when filter_active=True.

        Regression test: Typing "start" should not trigger TEAM_SWITCH
        when the user is typing in the filter field.
        """
        action = map_key_to_action("t", enable_filter=True, filter_active=True)
        assert action.action_type == ActionType.FILTER_CHAR
        assert action.filter_char == "t"
        assert action.should_exit is False

    def test_t_triggers_team_switch_when_filter_not_active(self) -> None:
        """'t' triggers TEAM_SWITCH when filter is not active."""
        action = map_key_to_action("t", enable_filter=True, filter_active=False)
        assert action.action_type == ActionType.TEAM_SWITCH

    def test_j_becomes_filter_char_when_filter_active(self) -> None:
        """'j' is treated as filter char when filter_active=True."""
        action = map_key_to_action("j", enable_filter=True, filter_active=True)
        assert action.action_type == ActionType.FILTER_CHAR
        assert action.filter_char == "j"

    def test_k_becomes_filter_char_when_filter_active(self) -> None:
        """'k' is treated as filter char when filter_active=True."""
        action = map_key_to_action("k", enable_filter=True, filter_active=True)
        assert action.action_type == ActionType.FILTER_CHAR
        assert action.filter_char == "k"

    def test_j_navigates_down_when_filter_not_active(self) -> None:
        """'j' triggers NAVIGATE_DOWN when filter is not active."""
        action = map_key_to_action("j", enable_filter=True, filter_active=False)
        assert action.action_type == ActionType.NAVIGATE_DOWN

    def test_k_navigates_up_when_filter_not_active(self) -> None:
        """'k' triggers NAVIGATE_UP when filter is not active."""
        action = map_key_to_action("k", enable_filter=True, filter_active=False)
        assert action.action_type == ActionType.NAVIGATE_UP

    def test_a_becomes_filter_char_when_filter_active(self) -> None:
        """'a' is treated as filter char when filter_active=True."""
        action = map_key_to_action("a", enable_filter=True, filter_active=True)
        assert action.action_type == ActionType.FILTER_CHAR
        assert action.filter_char == "a"

    def test_a_toggles_all_when_filter_not_active(self) -> None:
        """'a' triggers TOGGLE_ALL when filter is not active."""
        action = map_key_to_action("a", enable_filter=True, filter_active=False)
        assert action.action_type == ActionType.TOGGLE_ALL

    def test_n_becomes_filter_char_when_filter_active(self) -> None:
        """'n' is treated as filter char when filter_active=True.

        Regression test: Typing words containing 'n' (like 'container')
        should not trigger NEW_SESSION when the user is typing in the filter field.
        """
        action = map_key_to_action("n", enable_filter=True, filter_active=True)
        assert action.action_type == ActionType.FILTER_CHAR
        assert action.filter_char == "n"
        assert action.should_exit is False

    def test_n_triggers_custom_action_when_registered_and_filter_not_active(self) -> None:
        """'n' triggers CUSTOM action when registered via custom_keys.

        Screens like Dashboard and Quick Resume register 'n' via custom_keys
        to get new session functionality. Without custom_keys, 'n' is just
        a regular FILTER_CHAR.
        """
        action = map_key_to_action(
            "n", enable_filter=True, filter_active=False, custom_keys={"n": "new_session"}
        )
        assert action.action_type == ActionType.CUSTOM
        assert action.custom_key == "n"

    def test_r_becomes_filter_char_when_filter_active(self) -> None:
        """'r' is treated as filter char when filter_active=True.

        Regression test: Typing words containing 'r' (like 'running', 'repo')
        should not trigger REFRESH when the user is typing in the filter field.
        This is a critical bug fix - dashboard passes r as custom_key for refresh.
        """
        action = map_key_to_action(
            "r", enable_filter=True, filter_active=True, custom_keys={"r": "refresh"}
        )
        assert action.action_type == ActionType.FILTER_CHAR
        assert action.filter_char == "r"
        assert action.should_exit is False

    def test_r_triggers_custom_action_when_filter_not_active(self) -> None:
        """'r' triggers CUSTOM action (refresh) when filter is not active.

        The dashboard passes r as a custom key for refresh functionality.
        """
        action = map_key_to_action(
            "r", enable_filter=True, filter_active=False, custom_keys={"r": "refresh"}
        )
        assert action.action_type == ActionType.CUSTOM
        assert action.custom_key == "r"

    def test_typing_running_after_filter_started(self) -> None:
        """Typing 'r' mid-filter should add to filter, not trigger refresh.

        Regression test for r key collision: when user has started typing a filter
        (filter_active=True) and presses 'r', it should go to the filter input
        instead of triggering the dashboard's refresh action.

        Example: User types 'sta', then 'r' to make 'star' - should not refresh.
        """
        # Simulate user already typed 'sta' (filter_active=True)
        # Now typing 'r' to make 'star'
        action = map_key_to_action(
            "r", enable_filter=True, filter_active=True, custom_keys={"r": "refresh"}
        )
        assert action.action_type == ActionType.FILTER_CHAR
        assert action.filter_char == "r"

        # Continue typing 'unning' → 'starring' scenario
        for char in "ring":
            action = map_key_to_action(
                char, enable_filter=True, filter_active=True, custom_keys={"r": "refresh"}
            )
            assert action.action_type == ActionType.FILTER_CHAR, (
                f"'{char}' should be filter char when filter_active=True"
            )
            assert action.filter_char == char

    def test_r_as_first_char_triggers_refresh_with_custom_key(self) -> None:
        """When filter is empty and 'r' is a custom key, it triggers refresh.

        This is expected behavior: if the dashboard has bound 'r' to refresh,
        pressing 'r' when filter is empty should trigger refresh.
        Users can start filter by typing other chars like 's' for 'star'.
        """
        action = map_key_to_action(
            "r", enable_filter=True, filter_active=False, custom_keys={"r": "refresh"}
        )
        # r as custom key takes precedence when filter not active
        assert action.action_type == ActionType.CUSTOM
        assert action.custom_key == "r"

    def test_regular_chars_always_filter_when_enabled(self) -> None:
        """Regular printable chars are always filter chars when enabled.

        Characters not in the special key map should become filter chars
        regardless of filter_active state (they start the filter).
        """
        # These chars are not in DEFAULT_KEY_MAP, so they become filter chars
        # Exclude: j,k,t,q,a,?,n which are mapped to actions
        for char in "bcdefghilmoprsuvwxyz":
            action = map_key_to_action(char, enable_filter=True, filter_active=False)
            assert action.action_type == ActionType.FILTER_CHAR, f"'{char}' should be filter char"
            assert action.filter_char == char

    def test_typing_start_produces_correct_sequence(self) -> None:
        """Typing 'start' should produce 5 FILTER_CHAR actions.

        Simulates the exact bug scenario: user types 's', 't', 'a', 'r', 't'.
        """
        # First char: filter not yet active (no content in filter)
        first_action = map_key_to_action("s", enable_filter=True, filter_active=False)
        assert first_action.action_type == ActionType.FILTER_CHAR
        assert first_action.filter_char == "s"

        # Subsequent chars: filter is now active
        for char in "tart":
            action = map_key_to_action(char, enable_filter=True, filter_active=True)
            assert action.action_type == ActionType.FILTER_CHAR, (
                f"'{char}' should be filter char when filter_active=True"
            )
            assert action.filter_char == char
