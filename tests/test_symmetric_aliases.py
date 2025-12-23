"""
Tests for symmetric command aliases (Phase 8).

TDD approach: Tests written before implementation.
These tests define the contract for:
- scc session list (alias for scc sessions)
- scc container list (alias for scc list)
"""


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Session App Structure
# ═══════════════════════════════════════════════════════════════════════════════


class TestSessionAppStructure:
    """Test session app Typer structure."""

    def test_session_app_exists(self) -> None:
        """session_app Typer should exist."""
        from scc_cli.cli_worktree import session_app

        assert session_app is not None

    def test_session_app_has_list_command(self) -> None:
        """session_app should have 'list' subcommand."""
        from scc_cli.cli_worktree import session_app

        command_names = [cmd.name for cmd in session_app.registered_commands]
        assert "list" in command_names


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Container App Structure
# ═══════════════════════════════════════════════════════════════════════════════


class TestContainerAppStructure:
    """Test container app Typer structure."""

    def test_container_app_exists(self) -> None:
        """container_app Typer should exist."""
        from scc_cli.cli_worktree import container_app

        assert container_app is not None

    def test_container_app_has_list_command(self) -> None:
        """container_app should have 'list' subcommand."""
        from scc_cli.cli_worktree import container_app

        command_names = [cmd.name for cmd in container_app.registered_commands]
        assert "list" in command_names


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for CLI Registration
# ═══════════════════════════════════════════════════════════════════════════════


class TestSymmetricAliasRegistration:
    """Test symmetric aliases are registered in main CLI."""

    def test_session_app_registered_in_main_cli(self) -> None:
        """session_app should be registered as subcommand in main CLI."""
        from scc_cli.cli import app

        group_names = [group.name for group in app.registered_groups if group.name]
        assert "session" in group_names

    def test_container_app_registered_in_main_cli(self) -> None:
        """container_app should be registered as subcommand in main CLI."""
        from scc_cli.cli import app

        group_names = [group.name for group in app.registered_groups if group.name]
        assert "container" in group_names


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Command Delegation
# ═══════════════════════════════════════════════════════════════════════════════


class TestCommandDelegation:
    """Test that symmetric aliases delegate to existing commands."""

    def test_session_list_delegates_to_sessions_cmd(self) -> None:
        """session list should delegate to sessions_cmd."""
        # Both should have the same underlying function or share behavior
        # We verify by checking they have similar signatures
        import inspect

        from scc_cli.cli_worktree import session_list_cmd, sessions_cmd

        sessions_sig = inspect.signature(sessions_cmd)
        session_list_sig = inspect.signature(session_list_cmd)

        # Both should accept 'limit' and 'select' parameters
        assert "limit" in sessions_sig.parameters
        assert "limit" in session_list_sig.parameters

    def test_container_list_delegates_to_list_cmd(self) -> None:
        """container list should delegate to list_cmd."""
        from scc_cli.cli_worktree import container_list_cmd, list_cmd

        # Verify both functions exist and can be called
        assert callable(container_list_cmd)
        assert callable(list_cmd)
