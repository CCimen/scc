"""Tests for ui/list_screen.py - Core navigation engine.

Test Categories:
- ListItem tests
- ListState navigation tests
- ListMode behavior tests (SINGLE_SELECT, MULTI_SELECT)
- Filter behavior tests
- Scroll behavior tests
"""

from __future__ import annotations

from scc_cli.ui.list_screen import ListItem, ListMode, ListScreen, ListState


class TestListItem:
    """Test ListItem dataclass."""

    def test_list_item_with_minimal_fields(self) -> None:
        """ListItem can be created with only value and label."""
        item = ListItem(value="test", label="Test Label")

        assert item.value == "test"
        assert item.label == "Test Label"
        assert item.description == ""
        assert item.governance_status is None

    def test_list_item_with_governance_status(self) -> None:
        """ListItem can have governance_status for visual indicators."""
        item = ListItem(
            value="blocked",
            label="Blocked Item",
            governance_status="blocked",
        )

        assert item.governance_status == "blocked"

    def test_list_item_metadata_defaults_to_empty_dict(self) -> None:
        """ListItem.metadata defaults to empty dict."""
        item = ListItem(value="x", label="X")
        assert item.metadata == {}

    def test_list_item_with_full_fields(self) -> None:
        """ListItem can have all fields populated."""
        item = ListItem(
            value="full",
            label="Full Label",
            description="A description",
            metadata={"status": "active"},
            governance_status="warning",
        )

        assert item.value == "full"
        assert item.label == "Full Label"
        assert item.description == "A description"
        assert item.metadata == {"status": "active"}
        assert item.governance_status == "warning"


class TestListState:
    """Test ListState navigation logic."""

    def _make_items(self, labels: list[str]) -> list[ListItem[str]]:
        """Helper to create list items from labels."""
        return [ListItem(value=label, label=label) for label in labels]

    def test_filtered_items_returns_all_when_no_query(self) -> None:
        """filtered_items returns all items when filter_query is empty."""
        items = self._make_items(["Apple", "Banana", "Cherry"])
        state = ListState(items=items)

        assert len(state.filtered_items) == 3

    def test_filtered_items_matches_label(self) -> None:
        """filtered_items matches against item labels."""
        items = self._make_items(["Apple", "Banana", "Cherry"])
        state = ListState(items=items, filter_query="an")

        filtered = state.filtered_items
        assert len(filtered) == 1
        assert filtered[0].label == "Banana"

    def test_filtered_items_matches_description(self) -> None:
        """filtered_items matches against item descriptions."""
        items = [
            ListItem(value="a", label="Apple", description="red fruit"),
            ListItem(value="b", label="Banana", description="yellow fruit"),
        ]
        state = ListState(items=items, filter_query="red")

        filtered = state.filtered_items
        assert len(filtered) == 1
        assert filtered[0].label == "Apple"

    def test_filtered_items_case_insensitive(self) -> None:
        """Filter matching is case-insensitive."""
        items = self._make_items(["Apple", "BANANA", "cherry"])
        state = ListState(items=items, filter_query="BAN")

        filtered = state.filtered_items
        assert len(filtered) == 1
        assert filtered[0].label == "BANANA"

    def test_current_item_returns_item_at_cursor(self) -> None:
        """current_item returns the item at cursor position."""
        items = self._make_items(["A", "B", "C"])
        state = ListState(items=items, cursor=1)

        assert state.current_item is not None
        assert state.current_item.label == "B"

    def test_current_item_none_when_list_empty(self) -> None:
        """current_item returns None when list is empty."""
        state: ListState[str] = ListState(items=[])
        assert state.current_item is None

    def test_current_item_none_when_filter_empty(self) -> None:
        """current_item returns None when filter produces no matches."""
        items = self._make_items(["Apple", "Banana"])
        state = ListState(items=items, filter_query="xyz")

        assert state.current_item is None


class TestListStateCursorMovement:
    """Test ListState cursor movement."""

    def _make_items(self, count: int) -> list[ListItem[int]]:
        """Helper to create numbered items."""
        return [ListItem(value=i, label=f"Item {i}") for i in range(count)]

    def test_move_cursor_down(self) -> None:
        """Moving cursor down increases position."""
        items = self._make_items(5)
        state = ListState(items=items, cursor=0)

        changed = state.move_cursor(1)

        assert changed is True
        assert state.cursor == 1

    def test_move_cursor_up(self) -> None:
        """Moving cursor up decreases position."""
        items = self._make_items(5)
        state = ListState(items=items, cursor=2)

        changed = state.move_cursor(-1)

        assert changed is True
        assert state.cursor == 1

    def test_move_cursor_clamps_at_top(self) -> None:
        """Cursor cannot go below 0."""
        items = self._make_items(5)
        state = ListState(items=items, cursor=0)

        changed = state.move_cursor(-1)

        assert changed is False
        assert state.cursor == 0

    def test_move_cursor_clamps_at_bottom(self) -> None:
        """Cursor cannot exceed list length."""
        items = self._make_items(5)
        state = ListState(items=items, cursor=4)

        changed = state.move_cursor(1)

        assert changed is False
        assert state.cursor == 4

    def test_move_cursor_on_empty_list(self) -> None:
        """Moving cursor on empty list returns False."""
        state: ListState[str] = ListState(items=[])

        changed = state.move_cursor(1)

        assert changed is False


class TestListModeSingleSelect:
    """Test SINGLE_SELECT mode behavior."""

    def _make_items(self, labels: list[str]) -> list[ListItem[str]]:
        """Helper to create list items."""
        return [ListItem(value=label, label=label) for label in labels]

    def test_single_select_mode_default(self) -> None:
        """ListScreen defaults to SINGLE_SELECT mode."""
        items = self._make_items(["A", "B"])
        screen = ListScreen(items, title="Test")

        assert screen.mode == ListMode.SINGLE_SELECT

    def test_navigation_moves_cursor(self) -> None:
        """Navigation updates cursor position in state."""
        items = self._make_items(["A", "B", "C"])
        screen = ListScreen(items)

        # Simulate navigation
        screen.state.move_cursor(1)

        assert screen.state.cursor == 1
        assert screen.state.current_item is not None
        assert screen.state.current_item.label == "B"


class TestListModeMultiSelect:
    """Test MULTI_SELECT mode behavior."""

    def _make_items(self, labels: list[str]) -> list[ListItem[str]]:
        """Helper to create list items."""
        return [ListItem(value=label, label=label) for label in labels]

    def test_space_toggles_selection(self) -> None:
        """toggle_selection toggles current item selection."""
        items = self._make_items(["A", "B", "C"])
        state = ListState(items=items, cursor=1)

        # First toggle - select
        state.toggle_selection()
        assert 1 in state.selected

        # Second toggle - deselect
        state.toggle_selection()
        assert 1 not in state.selected

    def test_toggle_all_selects_all(self) -> None:
        """toggle_all selects all when none selected."""
        items = self._make_items(["A", "B", "C"])
        state = ListState(items=items)

        state.toggle_all()

        assert state.selected == {0, 1, 2}

    def test_toggle_all_deselects_when_all_selected(self) -> None:
        """toggle_all deselects all when all selected."""
        items = self._make_items(["A", "B", "C"])
        state = ListState(items=items, selected={0, 1, 2})

        state.toggle_all()

        assert state.selected == set()

    def test_multi_select_mode_creates_screen(self) -> None:
        """ListScreen can be created in MULTI_SELECT mode."""
        items = self._make_items(["A", "B"])
        screen = ListScreen(items, mode=ListMode.MULTI_SELECT)

        assert screen.mode == ListMode.MULTI_SELECT


class TestListModeActionable:
    """Test ACTIONABLE mode behavior."""

    def _make_items(self, labels: list[str]) -> list[ListItem[str]]:
        """Helper to create list items."""
        return [ListItem(value=label, label=label) for label in labels]

    def test_actionable_mode_accepts_custom_actions(self) -> None:
        """ListScreen accepts custom_actions parameter."""
        items = self._make_items(["A", "B"])
        actions_called: list[str] = []

        screen = ListScreen(
            items,
            mode=ListMode.ACTIONABLE,
            custom_actions={"s": lambda item: actions_called.append(item.label)},
        )

        assert "s" in screen.custom_actions


class TestFilterBehavior:
    """Test type-to-filter behavior."""

    def _make_items(self, labels: list[str]) -> list[ListItem[str]]:
        """Helper to create list items."""
        return [ListItem(value=label, label=label) for label in labels]

    def test_printable_chars_add_to_filter(self) -> None:
        """add_filter_char adds character to filter query."""
        items = self._make_items(["Apple", "Banana"])
        state = ListState(items=items)

        state.add_filter_char("a")
        state.add_filter_char("p")

        assert state.filter_query == "ap"

    def test_backspace_removes_from_filter(self) -> None:
        """delete_filter_char removes last character from filter."""
        items = self._make_items(["Apple", "Banana"])
        state = ListState(items=items, filter_query="app")

        state.delete_filter_char()

        assert state.filter_query == "ap"

    def test_filter_updates_visible_items(self) -> None:
        """Changing filter updates filtered items immediately."""
        items = self._make_items(["Apple", "Apricot", "Banana"])
        state = ListState(items=items)

        assert len(state.filtered_items) == 3

        state.add_filter_char("b")

        assert len(state.filtered_items) == 1
        assert state.filtered_items[0].label == "Banana"

    def test_filter_resets_cursor(self) -> None:
        """Adding filter character resets cursor to 0."""
        items = self._make_items(["Apple", "Banana", "Cherry"])
        state = ListState(items=items, cursor=2)

        state.add_filter_char("a")

        assert state.cursor == 0

    def test_empty_filter_result(self) -> None:
        """Empty filter result produces empty list."""
        items = self._make_items(["Apple", "Banana"])
        state = ListState(items=items, filter_query="xyz")

        assert len(state.filtered_items) == 0


class TestScrollBehavior:
    """Test scroll behavior with viewport."""

    def _make_items(self, count: int) -> list[ListItem[int]]:
        """Helper to create numbered items."""
        return [ListItem(value=i, label=f"Item {i}") for i in range(count)]

    def test_cursor_past_viewport_scrolls_down(self) -> None:
        """Moving cursor past viewport scrolls view down."""
        items = self._make_items(20)
        state = ListState(items=items, viewport_height=5, cursor=4)

        # Move cursor past viewport
        state.move_cursor(1)

        # Scroll should adjust to keep cursor visible
        assert state.cursor == 5
        assert state.scroll_offset > 0

    def test_cursor_before_viewport_scrolls_up(self) -> None:
        """Moving cursor before viewport scrolls view up."""
        items = self._make_items(20)
        state = ListState(items=items, viewport_height=5, cursor=5, scroll_offset=5)

        # Move cursor up past scroll offset
        state.move_cursor(-1)

        # Cursor moved up
        assert state.cursor == 4
        # scroll_offset adjusted if needed
        assert state.scroll_offset <= state.cursor

    def test_visible_items_respects_viewport_height(self) -> None:
        """visible_items returns at most viewport_height items."""
        items = self._make_items(20)
        state = ListState(items=items, viewport_height=5)

        assert len(state.visible_items) <= 5

    def test_visible_items_with_scroll_offset(self) -> None:
        """visible_items starts from scroll_offset."""
        items = self._make_items(20)
        state = ListState(items=items, viewport_height=5, scroll_offset=10)

        visible = state.visible_items
        assert visible[0].value == 10  # First visible is at offset


class TestListScreenRendering:
    """Test ListScreen rendering."""

    def _make_items(self, labels: list[str]) -> list[ListItem[str]]:
        """Helper to create list items."""
        return [ListItem(value=label, label=label) for label in labels]

    def test_render_list_body_includes_cursor(self) -> None:
        """Rendered list shows cursor indicator on current item."""
        items = self._make_items(["A", "B", "C"])
        screen = ListScreen(items, title="Test")

        body = screen._render_list_body()
        text = str(body)

        # Should have cursor indicator
        assert "❯" in text

    def test_render_empty_list_shows_message(self) -> None:
        """Rendered empty list shows 'No matches' message."""
        items = self._make_items(["Apple"])
        screen = ListScreen(items)
        screen.state.filter_query = "xyz"  # No matches

        body = screen._render_list_body()
        text = str(body)

        assert "No matches" in text


class TestListScreenChrome:
    """Test ListScreen chrome configuration."""

    def _make_items(self, labels: list[str]) -> list[ListItem[str]]:
        """Helper to create list items."""
        return [ListItem(value=label, label=label) for label in labels]

    def test_single_select_uses_picker_chrome(self) -> None:
        """SINGLE_SELECT mode uses picker chrome config."""
        items = self._make_items(["A", "B"])
        screen = ListScreen(items, mode=ListMode.SINGLE_SELECT)

        config = screen._get_chrome_config()

        assert config.show_tabs is False
        assert config.show_search is True

    def test_multi_select_uses_multi_select_chrome(self) -> None:
        """MULTI_SELECT mode uses multi-select chrome config."""
        items = self._make_items(["A", "B"])
        screen = ListScreen(items, mode=ListMode.MULTI_SELECT)

        config = screen._get_chrome_config()

        # Multi-select subtitle shows selection count
        assert "0" in config.subtitle
        assert "2" in config.subtitle
