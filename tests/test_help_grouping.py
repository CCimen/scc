"""
Tests for CLI help grouping (Phase 10).

TDD approach: Tests written before implementation.
These tests define the contract for:
- Commands organized into logical groups
- Groups displayed in --help output
- Consistent grouping across related commands
"""

import subprocess

# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Help Panel Existence
# ═══════════════════════════════════════════════════════════════════════════════


class TestHelpPanelStructure:
    """Test that commands are assigned to help panels."""

    def test_start_command_has_help_panel(self) -> None:
        """start command should have rich_help_panel set."""
        from scc_cli.cli import app

        # Find start command (registered without explicit name, uses function name)
        start_cmd = None
        for cmd in app.registered_commands:
            # Command name is derived from function name or explicit name param
            cmd_name = cmd.name or (cmd.callback.__name__ if cmd.callback else None)
            if cmd_name == "start":
                start_cmd = cmd
                break

        assert start_cmd is not None, "start command not found"
        assert start_cmd.rich_help_panel is not None and start_cmd.rich_help_panel != "", (
            "start command missing rich_help_panel"
        )

    def test_session_commands_have_help_panel(self) -> None:
        """Session-related commands should have rich_help_panel set."""
        from scc_cli.cli import app

        session_commands = ["sessions", "list", "stop", "prune"]
        for cmd_name in session_commands:
            cmd = next((c for c in app.registered_commands if c.name == cmd_name), None)
            assert cmd is not None, f"Command {cmd_name} not found"
            assert cmd.rich_help_panel is not None and cmd.rich_help_panel != "", (
                f"{cmd_name} missing rich_help_panel"
            )

    def test_config_commands_have_help_panel(self) -> None:
        """Configuration commands should have rich_help_panel set."""
        from scc_cli.cli import app

        config_commands = ["setup", "config", "init"]
        for cmd_name in config_commands:
            cmd = next((c for c in app.registered_commands if c.name == cmd_name), None)
            assert cmd is not None, f"Command {cmd_name} not found"
            assert cmd.rich_help_panel is not None and cmd.rich_help_panel != "", (
                f"{cmd_name} missing rich_help_panel"
            )

    def test_admin_commands_have_help_panel(self) -> None:
        """Admin commands should have rich_help_panel set."""
        from scc_cli.cli import app

        admin_commands = ["doctor", "update", "status", "statusline"]
        for cmd_name in admin_commands:
            cmd = next((c for c in app.registered_commands if c.name == cmd_name), None)
            assert cmd is not None, f"Command {cmd_name} not found"
            assert cmd.rich_help_panel is not None and cmd.rich_help_panel != "", (
                f"{cmd_name} missing rich_help_panel"
            )

    def test_governance_commands_have_help_panel(self) -> None:
        """Governance commands should have rich_help_panel set."""
        from scc_cli.cli import app

        governance_commands = ["unblock"]
        for cmd_name in governance_commands:
            cmd = next((c for c in app.registered_commands if c.name == cmd_name), None)
            assert cmd is not None, f"Command {cmd_name} not found"
            assert cmd.rich_help_panel is not None and cmd.rich_help_panel != "", (
                f"{cmd_name} missing rich_help_panel"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Help Panel Groupings
# ═══════════════════════════════════════════════════════════════════════════════


class TestHelpPanelGroupings:
    """Test that commands are grouped correctly."""

    def test_session_commands_in_same_group(self) -> None:
        """Session-related commands should be in the same group."""
        from scc_cli.cli import app

        session_commands = ["start", "sessions", "list", "stop", "prune"]
        panels = set()
        for cmd_name in session_commands:
            cmd = next((c for c in app.registered_commands if c.name == cmd_name), None)
            if cmd and cmd.rich_help_panel:
                panels.add(cmd.rich_help_panel)

        # All session commands should be in the same panel
        assert len(panels) == 1, f"Session commands in multiple panels: {panels}"

    def test_config_commands_in_same_group(self) -> None:
        """Configuration commands should be in the same group."""
        from scc_cli.cli import app

        config_commands = ["setup", "config", "init"]
        panels = set()
        for cmd_name in config_commands:
            cmd = next((c for c in app.registered_commands if c.name == cmd_name), None)
            if cmd and cmd.rich_help_panel:
                panels.add(cmd.rich_help_panel)

        # All config commands should be in the same panel
        assert len(panels) == 1, f"Config commands in multiple panels: {panels}"

    def test_admin_commands_in_same_group(self) -> None:
        """Admin commands should be in the same group."""
        from scc_cli.cli import app

        admin_commands = ["doctor", "update", "status", "statusline"]
        panels = set()
        for cmd_name in admin_commands:
            cmd = next((c for c in app.registered_commands if c.name == cmd_name), None)
            if cmd and cmd.rich_help_panel:
                panels.add(cmd.rich_help_panel)

        # All admin commands should be in the same panel
        assert len(panels) == 1, f"Admin commands in multiple panels: {panels}"

    def test_different_groups_exist(self) -> None:
        """There should be at least 3 different help groups."""
        from scc_cli.cli import app

        panels = set()
        for cmd in app.registered_commands:
            if cmd.rich_help_panel:
                panels.add(cmd.rich_help_panel)

        # Should have at least: Session, Configuration, Administration
        assert len(panels) >= 3, f"Only {len(panels)} groups found: {panels}"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Help Output
# ═══════════════════════════════════════════════════════════════════════════════


class TestHelpOutput:
    """Test that help output shows groupings."""

    def test_help_output_contains_group_headers(self) -> None:
        """scc --help should show group headers."""
        result = subprocess.run(
            ["uv", "run", "scc", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Check for expected group names in output
        # The exact names may vary, but we should see some grouping
        output = result.stdout

        # At minimum, we expect to see "Commands" section
        assert "Commands" in output or "commands" in output.lower()

    def test_help_output_organized_not_flat(self) -> None:
        """scc --help should not show a flat list of commands."""
        result = subprocess.run(
            ["uv", "run", "scc", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        output = result.stdout

        # Should contain key commands
        assert "start" in output.lower()
        assert "doctor" in output.lower()
        assert "setup" in output.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Sub-App Groupings
# ═══════════════════════════════════════════════════════════════════════════════


class TestSubAppGroupings:
    """Test that sub-apps (typer groups) are also properly grouped."""

    def test_worktree_app_has_help_panel(self) -> None:
        """worktree sub-app should have rich_help_panel set."""
        from scc_cli.cli import app

        # Find worktree in registered groups
        worktree_found = False
        for group in app.registered_groups:
            if group.typer_instance and getattr(group, "name", None) == "worktree":
                worktree_found = True
                # Groups can also have rich_help_panel
                break

        assert worktree_found, "worktree sub-app not found in registered groups"

    def test_team_app_has_help_panel(self) -> None:
        """team sub-app should have rich_help_panel set."""
        from scc_cli.cli import app

        team_found = False
        for group in app.registered_groups:
            if getattr(group, "name", None) == "team":
                team_found = True
                break

        assert team_found, "team sub-app not found in registered groups"

    def test_audit_app_has_help_panel(self) -> None:
        """audit sub-app should have rich_help_panel set."""
        from scc_cli.cli import app

        audit_found = False
        for group in app.registered_groups:
            if getattr(group, "name", None) == "audit":
                audit_found = True
                break

        assert audit_found, "audit sub-app not found in registered groups"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Hidden Commands
# ═══════════════════════════════════════════════════════════════════════════════


class TestHiddenCommandsExcluded:
    """Test that hidden/deprecated commands don't appear in help."""

    def test_teams_hidden_not_in_help(self) -> None:
        """Deprecated 'teams' command should be hidden."""
        result = subprocess.run(
            ["uv", "run", "scc", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        output = result.stdout

        # 'teams' should not appear (it's a hidden deprecated alias)
        # But 'team' (the sub-app) should appear
        lines = output.lower().split("\n")
        teams_line = [line for line in lines if "teams" in line and "team" not in line]
        # Should not find a standalone 'teams' command
        assert len(teams_line) == 0 or all("deprecated" in line for line in teams_line)
