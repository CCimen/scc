"""Tests for ui/chrome.py - Shared layout rendering.

Test Categories:
- ChromeConfig factory method tests
- render_chrome output tests
- Footer hints display tests
- Tab rendering tests
"""

from __future__ import annotations

from io import StringIO

from rich.console import Console
from rich.text import Text

from scc_cli.ui.chrome import Chrome, ChromeConfig, FooterHint, render_chrome


class TestChromeConfigFactoryMethods:
    """Test ChromeConfig factory methods."""

    def test_for_picker_creates_standard_picker_config(self) -> None:
        """for_picker() creates config with standard picker footer hints."""
        config = ChromeConfig.for_picker("Select Team", 5)

        assert config.title == "Select Team"
        assert config.show_tabs is False
        assert config.show_search is True
        # Check hints contain expected actions
        hint_actions = [h.action for h in config.footer_hints]
        assert "navigate" in hint_actions
        assert "select" in hint_actions
        assert "teams" in hint_actions
        assert "back" in hint_actions
        assert "quit" in hint_actions

    def test_for_picker_includes_item_count_in_subtitle(self) -> None:
        """for_picker() includes item count in subtitle when using deprecated item_count."""
        config = ChromeConfig.for_picker("Select Team", item_count=10)
        assert "10" in config.subtitle
        assert "available" in config.subtitle

    def test_for_picker_uses_subtitle_when_provided(self) -> None:
        """for_picker() uses explicit subtitle when provided."""
        config = ChromeConfig.for_picker("Select Team", "5 teams available")
        assert config.subtitle == "5 teams available"

    def test_for_multi_select_shows_selection_count(self) -> None:
        """for_multi_select() shows selected/total in subtitle."""
        config = ChromeConfig.for_multi_select("Stop Containers", 3, 10)
        assert "3" in config.subtitle
        assert "10" in config.subtitle
        assert "selected" in config.subtitle

    def test_for_multi_select_includes_toggle_hints(self) -> None:
        """for_multi_select() includes Space and 'a' toggle hints."""
        config = ChromeConfig.for_multi_select("Stop Containers", 0, 5)

        hint_keys = [h.key for h in config.footer_hints]
        hint_actions = [h.action for h in config.footer_hints]

        assert "Space" in hint_keys
        assert "a" in hint_keys
        assert "toggle" in hint_actions
        assert "toggle all" in hint_actions

    def test_for_dashboard_enables_tabs(self) -> None:
        """for_dashboard() creates config with show_tabs=True."""
        tabs = ["Status", "Containers", "Sessions"]
        config = ChromeConfig.for_dashboard(tabs, 0)

        assert config.show_tabs is True
        assert config.tabs == ("Status", "Containers", "Sessions")
        assert config.active_tab_index == 0

    def test_for_dashboard_stores_active_tab_index(self) -> None:
        """for_dashboard() stores the active tab index correctly."""
        tabs = ["Status", "Containers", "Sessions"]
        config = ChromeConfig.for_dashboard(tabs, 2)

        assert config.active_tab_index == 2


class TestRenderChrome:
    """Test render_chrome() output structure."""

    def _render_to_string(self, renderable: object) -> str:
        """Helper to render Rich content to plain string."""
        console = Console(file=StringIO(), force_terminal=True, width=80)
        console.print(renderable)
        return console.file.getvalue()  # type: ignore[union-attr]

    def test_render_chrome_includes_title(self) -> None:
        """Rendered chrome includes the title."""
        config = ChromeConfig(title="Test Title")
        body = Text("Body content")

        result = render_chrome(config, body)
        output = self._render_to_string(result)

        assert "Test Title" in output

    def test_render_chrome_includes_subtitle(self) -> None:
        """Rendered chrome includes subtitle when provided."""
        config = ChromeConfig(title="Title", subtitle="5 items")
        body = Text("Body")

        result = render_chrome(config, body)
        output = self._render_to_string(result)

        assert "5 items" in output

    def test_render_chrome_shows_search_query(self) -> None:
        """Rendered chrome shows search query when provided."""
        config = ChromeConfig(title="Title", show_search=True)
        body = Text("Body")

        result = render_chrome(config, body, search_query="test")
        output = self._render_to_string(result)

        assert "test" in output

    def test_render_chrome_includes_body(self) -> None:
        """Rendered chrome includes the body content."""
        config = ChromeConfig(title="Title")
        body = Text("Unique body content here")

        result = render_chrome(config, body)
        output = self._render_to_string(result)

        assert "Unique body content here" in output

    def test_render_chrome_includes_footer_hints(self) -> None:
        """Rendered chrome includes footer hints."""
        config = ChromeConfig(
            title="Title",
            footer_hints=(
                FooterHint("Enter", "select"),
                FooterHint("q", "quit"),
            ),
        )
        body = Text("Body")

        result = render_chrome(config, body)
        output = self._render_to_string(result)

        assert "Enter" in output
        assert "select" in output
        assert "quit" in output

    def test_render_chrome_includes_context_label(self) -> None:
        """Rendered chrome includes context_label when provided."""
        config = ChromeConfig(title="Select", context_label="platform · api · main")
        body = Text("Body")

        result = render_chrome(config, body)
        output = self._render_to_string(result)

        assert "platform · api · main" in output

    def test_render_chrome_title_format_with_context_only(self) -> None:
        """Title format is 'Title │ context_label' when no subtitle."""
        config = ChromeConfig(title="Select Team", context_label="platform · api")
        body = Text("Body")

        result = render_chrome(config, body)
        output = self._render_to_string(result)

        # Both should appear in title, separated by │
        assert "Select Team" in output
        assert "platform · api" in output
        assert "│" in output

    def test_render_chrome_title_format_with_context_and_subtitle(self) -> None:
        """Title format is 'Title │ context_label │ subtitle' when both provided."""
        config = ChromeConfig(
            title="Select Team",
            context_label="platform · api",
            subtitle="5 available",
        )
        body = Text("Body")

        result = render_chrome(config, body)
        output = self._render_to_string(result)

        # All three should appear
        assert "Select Team" in output
        assert "platform · api" in output
        assert "5 available" in output


class TestTabRendering:
    """Test tab row rendering in chrome."""

    def _render_to_string(self, renderable: object) -> str:
        """Helper to render Rich content to plain string."""
        console = Console(file=StringIO(), force_terminal=True, width=80)
        console.print(renderable)
        return console.file.getvalue()  # type: ignore[union-attr]

    def test_render_chrome_with_tabs_shows_tab_row(self) -> None:
        """Tabs are rendered when show_tabs=True."""
        config = ChromeConfig(
            title="Dashboard",
            show_tabs=True,
            tabs=("Status", "Containers"),
            active_tab_index=0,
        )
        body = Text("Body")

        result = render_chrome(config, body)
        output = self._render_to_string(result)

        assert "Status" in output
        assert "Containers" in output

    def test_render_chrome_without_tabs_hides_tab_row(self) -> None:
        """Tab row is hidden when show_tabs=False."""
        config = ChromeConfig(
            title="Picker",
            show_tabs=False,
            tabs=("Hidden1", "Hidden2"),  # Even if tabs provided
        )
        body = Text("Body")

        result = render_chrome(config, body)
        output = self._render_to_string(result)

        # Tabs shouldn't appear in output
        assert "Hidden1" not in output
        assert "Hidden2" not in output

    def test_active_tab_is_highlighted(self) -> None:
        """Active tab is visually distinguished from inactive tabs."""
        config = ChromeConfig(
            title="Dashboard",
            show_tabs=True,
            tabs=("Status", "Containers", "Sessions"),
            active_tab_index=1,
        )

        chrome = Chrome(config)
        tab_row = chrome._render_tabs()

        # The active tab (index 1 = Containers) should be styled differently
        # Check that Containers is bracketed (our active indicator)
        assert "[Containers]" in str(tab_row)


class TestFooterHintsDisplay:
    """Test footer hints rendering."""

    def _render_to_string(self, renderable: object) -> str:
        """Helper to render Rich content to plain string."""
        console = Console(file=StringIO(), force_terminal=True, width=80)
        console.print(renderable)
        return console.file.getvalue()  # type: ignore[union-attr]

    def test_footer_hints_joined_with_separator(self) -> None:
        """Footer hints are joined with visual separator."""
        config = ChromeConfig(
            title="Title",
            footer_hints=(
                FooterHint("↑↓", "navigate"),
                FooterHint("Enter", "select"),
            ),
        )
        body = Text("Body")

        result = render_chrome(config, body)
        output = self._render_to_string(result)

        # Should have separator between hints
        assert "│" in output

    def test_footer_hint_shows_key_and_action(self) -> None:
        """Each hint shows both key and action description."""
        config = ChromeConfig(
            title="Title",
            footer_hints=(FooterHint("Space", "toggle"),),
        )
        body = Text("Body")

        result = render_chrome(config, body)
        output = self._render_to_string(result)

        assert "Space" in output
        assert "toggle" in output

    def test_empty_footer_hints_renders_no_footer(self) -> None:
        """Empty footer_hints list renders no footer row."""
        config = ChromeConfig(title="Title", footer_hints=())
        body = Text("Body")

        result = render_chrome(config, body)
        output = self._render_to_string(result)

        # Should not have the separator line that precedes hints
        # (This is a bit fragile, but we check for absence of hint-specific content)
        assert "navigate" not in output


class TestSearchRowRendering:
    """Test search row rendering behavior."""

    def _render_to_string(self, renderable: object) -> str:
        """Helper to render Rich content to plain string."""
        console = Console(file=StringIO(), force_terminal=True, width=80)
        console.print(renderable)
        return console.file.getvalue()  # type: ignore[union-attr]

    def test_search_row_shows_placeholder_when_empty(self) -> None:
        """Search row shows placeholder text when query is empty."""
        config = ChromeConfig(title="Title", show_search=True)
        body = Text("Body")

        result = render_chrome(config, body, search_query="")
        output = self._render_to_string(result)

        assert "Type to filter" in output

    def test_search_row_shows_query_when_provided(self) -> None:
        """Search row shows the query when provided."""
        config = ChromeConfig(title="Title", show_search=True)
        body = Text("Body")

        result = render_chrome(config, body, search_query="my-search")
        output = self._render_to_string(result)

        assert "my-search" in output


class TestFooterHintDataclass:
    """Test FooterHint dataclass."""

    def test_footer_hint_is_frozen(self) -> None:
        """FooterHint is immutable (frozen)."""
        hint = FooterHint("Enter", "select")
        try:
            hint.key = "Space"  # type: ignore[misc]
            raise AssertionError("Should have raised FrozenInstanceError")
        except AttributeError:
            pass  # Expected


class TestChromeConfigDataclass:
    """Test ChromeConfig dataclass."""

    def test_chrome_config_is_frozen(self) -> None:
        """ChromeConfig is immutable (frozen)."""
        config = ChromeConfig(title="Test")
        try:
            config.title = "Changed"  # type: ignore[misc]
            raise AssertionError("Should have raised FrozenInstanceError")
        except AttributeError:
            pass  # Expected

    def test_chrome_config_defaults(self) -> None:
        """ChromeConfig has sensible defaults."""
        config = ChromeConfig(title="Minimal")

        assert config.subtitle == ""
        assert config.context_label == ""
        assert config.show_tabs is False
        assert config.tabs == ()
        assert config.active_tab_index == 0
        assert config.show_search is True
        assert config.footer_hints == ()

    def test_with_context_creates_new_config(self) -> None:
        """with_context() creates new config with context_label set."""
        original = ChromeConfig.for_picker("Select Team", item_count=5)
        updated = original.with_context("platform · api · main")

        assert updated.context_label == "platform · api · main"
        # Original unchanged (frozen dataclass)
        assert original.context_label == ""

    def test_with_context_preserves_other_fields(self) -> None:
        """with_context() preserves all other config fields."""
        original = ChromeConfig(
            title="Test",
            subtitle="5 items",
            show_tabs=True,
            tabs=("A", "B"),
            active_tab_index=1,
            show_search=False,
            footer_hints=(FooterHint("q", "quit"),),
        )
        updated = original.with_context("team · repo · wt")

        assert updated.title == "Test"
        assert updated.subtitle == "5 items"
        assert updated.context_label == "team · repo · wt"
        assert updated.show_tabs is True
        assert updated.tabs == ("A", "B")
        assert updated.active_tab_index == 1
        assert updated.show_search is False
        assert updated.footer_hints == (FooterHint("q", "quit"),)
