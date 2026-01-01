"""
Tests for worktree CLI commands (Phase 5).

TDD approach: Tests written before implementation.
These tests define the contract for:
- scc worktree create
- scc worktree list (with --json)
- scc worktree remove
- Deprecated aliases (scc worktrees, scc cleanup)
"""

import json
from pathlib import Path
from unittest.mock import patch

import click
import pytest

from scc_cli.git import WorktreeInfo, render_worktrees

# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Worktree CLI Structure
# ═══════════════════════════════════════════════════════════════════════════════


class TestWorktreeAppStructure:
    """Test worktree app Typer structure."""

    def test_worktree_app_exists(self) -> None:
        """worktree_app Typer should exist."""
        from scc_cli.cli_worktree import worktree_app

        assert worktree_app is not None

    def test_worktree_app_has_create_command(self) -> None:
        """worktree_app should have 'create' subcommand."""
        from scc_cli.cli_worktree import worktree_app

        command_names = [cmd.name for cmd in worktree_app.registered_commands]
        assert "create" in command_names

    def test_worktree_app_has_list_command(self) -> None:
        """worktree_app should have 'list' subcommand."""
        from scc_cli.cli_worktree import worktree_app

        command_names = [cmd.name for cmd in worktree_app.registered_commands]
        assert "list" in command_names

    def test_worktree_app_has_remove_command(self) -> None:
        """worktree_app should have 'remove' subcommand."""
        from scc_cli.cli_worktree import worktree_app

        command_names = [cmd.name for cmd in worktree_app.registered_commands]
        assert "remove" in command_names


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Worktree Create Command
# ═══════════════════════════════════════════════════════════════════════════════


class TestWorktreeCreate:
    """Test scc worktree create command."""

    def test_create_calls_git_create_worktree(self, tmp_path: Path) -> None:
        """create should call git.create_worktree with correct args."""
        from scc_cli.cli_worktree import worktree_create_cmd

        with (
            patch("scc_cli.cli_worktree.git.is_git_repo", return_value=True),
            patch("scc_cli.cli_worktree.git.create_worktree") as mock_create,
            patch("scc_cli.cli_worktree.Confirm.ask", return_value=False),
        ):
            mock_create.return_value = tmp_path / "worktrees" / "feature"
            try:
                worktree_create_cmd(
                    workspace=str(tmp_path),
                    name="feature",
                    base_branch=None,
                    start_claude=False,
                    install_deps=False,
                )
            except click.exceptions.Exit:
                pass

            mock_create.assert_called_once()
            call_args = mock_create.call_args
            assert call_args[0][1] == "feature"

    def test_create_with_base_branch(self, tmp_path: Path) -> None:
        """create with --base should pass branch to git.create_worktree."""
        from scc_cli.cli_worktree import worktree_create_cmd

        with (
            patch("scc_cli.cli_worktree.git.is_git_repo", return_value=True),
            patch("scc_cli.cli_worktree.git.create_worktree") as mock_create,
            patch("scc_cli.cli_worktree.Confirm.ask", return_value=False),
        ):
            mock_create.return_value = tmp_path / "worktrees" / "feature"
            try:
                worktree_create_cmd(
                    workspace=str(tmp_path),
                    name="feature",
                    base_branch="develop",
                    start_claude=False,
                    install_deps=False,
                )
            except click.exceptions.Exit:
                pass

            call_args = mock_create.call_args
            assert call_args[0][2] == "develop"

    def test_create_raises_for_non_repo(self, tmp_path: Path) -> None:
        """create should exit with error for non-git directories."""
        from scc_cli.cli_worktree import worktree_create_cmd

        with patch("scc_cli.cli_worktree.git.is_git_repo", return_value=False):
            # @handle_errors decorator converts NotAGitRepoError to typer.Exit(4)
            with pytest.raises(click.exceptions.Exit) as exc_info:
                worktree_create_cmd(
                    workspace=str(tmp_path),
                    name="feature",
                    base_branch=None,
                    start_claude=False,
                    install_deps=False,
                )
            assert exc_info.value.exit_code == 4


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Worktree List Command
# ═══════════════════════════════════════════════════════════════════════════════


class TestWorktreeList:
    """Test scc worktree list command."""

    def test_list_calls_git_list_worktrees(self, tmp_path: Path) -> None:
        """list should call git.list_worktrees."""
        from scc_cli.cli_worktree import worktree_list_cmd

        with (
            patch("scc_cli.cli_worktree.git.list_worktrees") as mock_list,
            patch("scc_cli.cli_worktree.git.render_worktrees"),
        ):
            mock_list.return_value = [
                WorktreeInfo(path=str(tmp_path), branch="main", status="clean")
            ]
            try:
                worktree_list_cmd(
                    workspace=str(tmp_path),
                    json_output=False,
                    pretty=False,
                )
            except click.exceptions.Exit:
                pass

            mock_list.assert_called_once()

    def test_list_json_has_correct_kind(self, tmp_path: Path, capsys) -> None:
        """list --json should output JSON with kind=WorktreeList."""
        from scc_cli.cli_worktree import worktree_list_cmd

        with (
            patch("scc_cli.cli_worktree.git.list_worktrees") as mock_list,
            patch("scc_cli.cli_worktree.git.render_worktrees"),
        ):
            mock_list.return_value = [
                WorktreeInfo(path=str(tmp_path), branch="main", status="clean")
            ]
            try:
                worktree_list_cmd(
                    workspace=str(tmp_path),
                    json_output=True,
                    pretty=False,
                )
            except click.exceptions.Exit:
                pass

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["kind"] == "WorktreeList"
        assert output["apiVersion"] == "scc.cli/v1"

    def test_list_json_contains_worktrees(self, tmp_path: Path, capsys) -> None:
        """list --json should contain worktree data."""
        from scc_cli.cli_worktree import worktree_list_cmd

        worktrees = [
            WorktreeInfo(path=str(tmp_path), branch="main", status="clean"),
            WorktreeInfo(path=str(tmp_path / "feature"), branch="feature/x", status="clean"),
        ]

        with (
            patch("scc_cli.cli_worktree.git.list_worktrees") as mock_list,
            patch("scc_cli.cli_worktree.git.render_worktrees"),
        ):
            mock_list.return_value = worktrees
            try:
                worktree_list_cmd(
                    workspace=str(tmp_path),
                    json_output=True,
                    pretty=False,
                )
            except click.exceptions.Exit:
                pass

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "worktrees" in output["data"]
        assert len(output["data"]["worktrees"]) == 2

    def test_list_json_empty_worktrees(self, tmp_path: Path, capsys) -> None:
        """list --json with no worktrees should return empty array."""
        from scc_cli.cli_worktree import worktree_list_cmd

        with (
            patch("scc_cli.cli_worktree.git.list_worktrees") as mock_list,
            patch("scc_cli.cli_worktree.git.render_worktrees"),
        ):
            mock_list.return_value = []
            try:
                worktree_list_cmd(
                    workspace=str(tmp_path),
                    json_output=True,
                    pretty=False,
                )
            except click.exceptions.Exit:
                pass

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["data"]["worktrees"] == []
        assert output["data"]["count"] == 0

    def test_render_worktrees_detached_branch_shows_label(self) -> None:
        """Detached worktrees should show a 'detached' label instead of blank."""
        from rich.console import Console

        console = Console(record=True, width=120)
        worktrees = [WorktreeInfo(path="/repo", branch="", status="")]

        render_worktrees(worktrees, console)

        output = console.export_text()
        assert "detached" in output.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Worktree Remove Command
# ═══════════════════════════════════════════════════════════════════════════════


class TestWorktreeRemove:
    """Test scc worktree remove command."""

    def test_remove_calls_git_cleanup_worktree(self, tmp_path: Path) -> None:
        """remove should call git.cleanup_worktree with correct args."""
        from scc_cli.cli_worktree import worktree_remove_cmd

        with patch("scc_cli.cli_worktree.git.cleanup_worktree") as mock_cleanup:
            mock_cleanup.return_value = True
            try:
                worktree_remove_cmd(
                    workspace=str(tmp_path),
                    name="feature",
                    force=False,
                )
            except click.exceptions.Exit:
                pass

            mock_cleanup.assert_called_once()
            call_args = mock_cleanup.call_args
            assert call_args[0][1] == "feature"

    def test_remove_with_force_flag(self, tmp_path: Path) -> None:
        """remove with --force should pass force=True to cleanup."""
        from scc_cli.cli_worktree import worktree_remove_cmd

        with patch("scc_cli.cli_worktree.git.cleanup_worktree") as mock_cleanup:
            mock_cleanup.return_value = True
            try:
                worktree_remove_cmd(
                    workspace=str(tmp_path),
                    name="feature",
                    force=True,
                )
            except click.exceptions.Exit:
                pass

            call_args = mock_cleanup.call_args
            assert call_args[0][2] is True  # force=True


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for CLI Integration
# ═══════════════════════════════════════════════════════════════════════════════


class TestWorktreeAppRegistration:
    """Test worktree app is registered in main CLI."""

    def test_worktree_app_registered_in_main_cli(self) -> None:
        """worktree_app should be registered as subcommand in main CLI."""
        from scc_cli.cli import app

        # Typer apps added via add_typer appear in registered_groups, not registered_commands
        group_names = [group.name for group in app.registered_groups if group.name]
        assert "worktree" in group_names


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Pure Functions
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildWorktreeListData:
    """Test build_worktree_list_data pure function."""

    def test_builds_correct_structure(self) -> None:
        """build_worktree_list_data should return correct structure."""
        from scc_cli.cli_worktree import build_worktree_list_data

        worktrees = [
            {"path": "/home/user/repo", "branch": "main", "head": "abc123"},
            {"path": "/home/user/repo-feature", "branch": "feature/x", "head": "def456"},
        ]
        result = build_worktree_list_data(worktrees, workspace="/home/user/repo")

        assert "worktrees" in result
        assert "count" in result
        assert "workspace" in result
        assert result["count"] == 2
        assert result["workspace"] == "/home/user/repo"

    def test_handles_empty_list(self) -> None:
        """build_worktree_list_data should handle empty list."""
        from scc_cli.cli_worktree import build_worktree_list_data

        result = build_worktree_list_data([], workspace="/home/user/repo")

        assert result["worktrees"] == []
        assert result["count"] == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Worktree Switch Command
# ═══════════════════════════════════════════════════════════════════════════════


class TestWorktreeSwitchCommand:
    """Test scc worktree switch command."""

    def test_switch_app_has_switch_command(self) -> None:
        """worktree_app should have 'switch' subcommand."""
        from scc_cli.cli_worktree import worktree_app

        command_names = [cmd.name for cmd in worktree_app.registered_commands]
        assert "switch" in command_names

    def test_switch_dash_uses_oldpwd(self, tmp_path: Path, capsys) -> None:
        """switch - should print $OLDPWD."""
        from scc_cli.cli_worktree import worktree_switch_cmd

        with (
            patch("scc_cli.cli_worktree.git.is_git_repo", return_value=True),
            patch.dict("os.environ", {"OLDPWD": "/previous/path"}),
        ):
            worktree_switch_cmd(target="-", workspace=str(tmp_path))

        captured = capsys.readouterr()
        assert captured.out.strip() == "/previous/path"

    def test_switch_dash_without_oldpwd_exits(self, tmp_path: Path) -> None:
        """switch - without $OLDPWD should exit with error."""
        from scc_cli.cli_worktree import worktree_switch_cmd

        with (
            patch("scc_cli.cli_worktree.git.is_git_repo", return_value=True),
            patch.dict("os.environ", {}, clear=True),
        ):
            with pytest.raises(click.exceptions.Exit) as exc_info:
                worktree_switch_cmd(target="-", workspace=str(tmp_path))
            assert exc_info.value.exit_code == 1

    def test_switch_caret_uses_main_worktree(self, tmp_path: Path, capsys) -> None:
        """switch ^ should print main branch worktree path."""
        from scc_cli.cli_worktree import worktree_switch_cmd

        main_wt = WorktreeInfo(path="/repo/main", branch="main", status="clean")
        with (
            patch("scc_cli.cli_worktree.git.is_git_repo", return_value=True),
            patch("scc_cli.cli_worktree.git.find_main_worktree", return_value=main_wt),
        ):
            worktree_switch_cmd(target="^", workspace=str(tmp_path))

        captured = capsys.readouterr()
        assert captured.out.strip() == "/repo/main"

    def test_switch_caret_without_main_worktree_exits(self, tmp_path: Path) -> None:
        """switch ^ without main worktree should exit with error."""
        from scc_cli.cli_worktree import worktree_switch_cmd

        with (
            patch("scc_cli.cli_worktree.git.is_git_repo", return_value=True),
            patch("scc_cli.cli_worktree.git.find_main_worktree", return_value=None),
            patch("scc_cli.cli_worktree.git.get_default_branch", return_value="main"),
        ):
            with pytest.raises(click.exceptions.Exit) as exc_info:
                worktree_switch_cmd(target="^", workspace=str(tmp_path))
            assert exc_info.value.exit_code == 1

    def test_switch_fuzzy_match_exact(self, tmp_path: Path, capsys) -> None:
        """switch with exact match should print worktree path."""
        from scc_cli.cli_worktree import worktree_switch_cmd

        feature_wt = WorktreeInfo(path="/repo/feature", branch="feature", status="clean")
        with (
            patch("scc_cli.cli_worktree.git.is_git_repo", return_value=True),
            patch(
                "scc_cli.cli_worktree.git.find_worktree_by_query",
                return_value=(feature_wt, [feature_wt]),
            ),
        ):
            worktree_switch_cmd(target="feature", workspace=str(tmp_path))

        captured = capsys.readouterr()
        assert captured.out.strip() == "/repo/feature"

    def test_switch_no_match_exits(self, tmp_path: Path) -> None:
        """switch with no match should exit with error."""
        from scc_cli.cli_worktree import worktree_switch_cmd

        with (
            patch("scc_cli.cli_worktree.git.is_git_repo", return_value=True),
            patch("scc_cli.cli_worktree.git.find_worktree_by_query", return_value=(None, [])),
            patch("scc_cli.cli_worktree.git.list_branches_without_worktrees", return_value=[]),
        ):
            with pytest.raises(click.exceptions.Exit) as exc_info:
                worktree_switch_cmd(target="nonexistent", workspace=str(tmp_path))
            assert exc_info.value.exit_code == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Worktree Switch Stdout Purity (Shell Integration)
# ═══════════════════════════════════════════════════════════════════════════════


class TestWorktreeSwitchStdoutPurity:
    """Ensure stdout contains ONLY the path for shell integration.

    The shell wrapper `wt() { cd "$(scc worktree switch "$@")" }` requires:
    - Success: stdout = exactly one line with the path (no trailing newlines)
    - Error: stdout = empty (all messages to stderr)
    - Cancel: stdout = empty
    """

    def test_success_stdout_is_exactly_path(self, tmp_path: Path, capsys) -> None:
        """On success, stdout should be exactly the path with one newline."""
        from scc_cli.cli_worktree import worktree_switch_cmd

        feature_wt = WorktreeInfo(path="/repo/feature", branch="feature", status="clean")
        with (
            patch("scc_cli.cli_worktree.git.is_git_repo", return_value=True),
            patch(
                "scc_cli.cli_worktree.git.find_worktree_by_query",
                return_value=(feature_wt, [feature_wt]),
            ),
        ):
            worktree_switch_cmd(target="feature", workspace=str(tmp_path))

        captured = capsys.readouterr()
        # stdout should be exactly the path with single newline (from print())
        assert captured.out == "/repo/feature\n"
        # No extra lines, no trailing spaces
        assert captured.out.count("\n") == 1

    def test_error_stdout_is_empty(self, tmp_path: Path, capsys) -> None:
        """On error (not found), stdout should be empty."""
        from scc_cli.cli_worktree import worktree_switch_cmd

        with (
            patch("scc_cli.cli_worktree.git.is_git_repo", return_value=True),
            patch("scc_cli.cli_worktree.git.find_worktree_by_query", return_value=(None, [])),
            patch("scc_cli.cli_worktree.git.list_branches_without_worktrees", return_value=[]),
        ):
            with pytest.raises(click.exceptions.Exit):
                worktree_switch_cmd(target="nonexistent", workspace=str(tmp_path))

        captured = capsys.readouterr()
        # stdout must be empty - all error output goes to stderr via console
        assert captured.out == ""

    def test_dash_shortcut_stdout_is_exactly_path(self, tmp_path: Path, capsys) -> None:
        """The '-' shortcut should print OLDPWD to stdout."""
        from scc_cli.cli_worktree import worktree_switch_cmd

        with (
            patch("scc_cli.cli_worktree.git.is_git_repo", return_value=True),
            patch.dict("os.environ", {"OLDPWD": "/previous/path"}),
        ):
            worktree_switch_cmd(target="-", workspace=str(tmp_path))

        captured = capsys.readouterr()
        assert captured.out == "/previous/path\n"
        assert captured.out.count("\n") == 1


class TestWorktreeSelectStdoutPurity:
    """Ensure worktree select maintains stdout/stderr contract.

    In non-interactive mode, error messages go to stderr, stdout stays clean.
    """

    def test_select_no_worktrees_has_actionable_error(self, tmp_path: Path, capsys) -> None:
        """On error (no worktrees), output should have actionable message."""
        from scc_cli.cli_worktree import worktree_select_cmd
        from scc_cli.ui.gate import InteractivityContext, InteractivityMode

        # Create a context that disallows prompts (non-interactive mode)
        mock_ctx = InteractivityContext(
            mode=InteractivityMode.NON_INTERACTIVE,
            is_json_output=False,
            force_yes=False,
        )

        with (
            patch("scc_cli.cli_worktree.git.is_git_repo", return_value=True),
            patch("scc_cli.cli_worktree.git.list_worktrees", return_value=[]),
            patch("scc_cli.cli_worktree.git.list_branches_without_worktrees", return_value=[]),
            patch("scc_cli.ui.gate.InteractivityContext.create", return_value=mock_ctx),
        ):
            with pytest.raises((click.exceptions.Exit, SystemExit)) as exc_info:
                worktree_select_cmd(workspace=str(tmp_path), branches=False)
            # Should exit with error
            exit_code = getattr(exc_info.value, "code", None) or getattr(
                exc_info.value, "exit_code", None
            )
            assert exit_code == 1

        captured = capsys.readouterr()
        # stdout should be empty (all output to stderr)
        assert captured.out == ""
        # stderr should have actionable message
        assert "No Worktrees" in captured.err or "worktree" in captured.err.lower()


class TestWorktreeListJsonContract:
    """Ensure worktree list --json outputs valid JSON."""

    def test_list_json_output_is_valid(self, tmp_path: Path) -> None:
        """--json flag should output valid JSON."""
        from typer.testing import CliRunner

        from scc_cli.cli import app

        runner = CliRunner()

        worktrees = [
            WorktreeInfo(path=str(tmp_path / "main"), branch="main", status="clean"),
            WorktreeInfo(path=str(tmp_path / "feature"), branch="feature", status="clean"),
        ]
        with (
            patch("scc_cli.cli_worktree.git.is_git_repo", return_value=True),
            patch("scc_cli.cli_worktree.git.list_worktrees", return_value=worktrees),
        ):
            result = runner.invoke(app, ["worktree", "list", str(tmp_path), "--json"])

        # Should succeed
        assert result.exit_code == 0
        # Output should be valid JSON
        assert result.output.strip()  # Not empty
        data = json.loads(result.output)  # Should parse without error
        assert "WorktreeList" in data.get("kind", "") or "worktree" in data.get("kind", "").lower()

    def test_list_json_contains_worktree_data(self, tmp_path: Path) -> None:
        """--json output should contain worktree data."""
        from typer.testing import CliRunner

        from scc_cli.cli import app

        runner = CliRunner()

        worktrees = [WorktreeInfo(path=str(tmp_path / "main"), branch="main", status="")]
        with (
            patch("scc_cli.cli_worktree.git.is_git_repo", return_value=True),
            patch("scc_cli.cli_worktree.git.list_worktrees", return_value=worktrees),
        ):
            result = runner.invoke(app, ["worktree", "list", str(tmp_path), "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        # Should contain worktree data
        assert "data" in data
        assert "worktrees" in data["data"] or len(data["data"]) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Worktree Select Command
# ═══════════════════════════════════════════════════════════════════════════════


class TestWorktreeSelectCommand:
    """Test scc worktree select command."""

    def test_select_app_has_select_command(self) -> None:
        """worktree_app should have 'select' subcommand."""
        from scc_cli.cli_worktree import worktree_app

        command_names = [cmd.name for cmd in worktree_app.registered_commands]
        assert "select" in command_names

    def test_select_no_worktrees_exits(self, tmp_path: Path) -> None:
        """select with no worktrees should exit with error."""
        from scc_cli.cli_worktree import worktree_select_cmd

        with (
            patch("scc_cli.cli_worktree.git.is_git_repo", return_value=True),
            patch("scc_cli.cli_worktree.git.list_worktrees", return_value=[]),
        ):
            with pytest.raises(click.exceptions.Exit) as exc_info:
                worktree_select_cmd(workspace=str(tmp_path), branches=False)
            assert exc_info.value.exit_code == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Git Fuzzy Matching Functions
# ═══════════════════════════════════════════════════════════════════════════════


class TestFindWorktreeByQuery:
    """Test find_worktree_by_query fuzzy matching."""

    def test_exact_branch_match(self, tmp_path: Path) -> None:
        """Exact branch name match should return single result."""
        from scc_cli.git import find_worktree_by_query

        worktrees = [
            WorktreeInfo(path=str(tmp_path / "main"), branch="main", status=""),
            WorktreeInfo(path=str(tmp_path / "feature"), branch="feature/auth", status=""),
        ]
        with patch("scc_cli.git._get_worktrees_data", return_value=worktrees):
            exact, matches = find_worktree_by_query(tmp_path, "main")

        assert exact is not None
        assert exact.branch == "main"

    def test_partial_branch_match(self, tmp_path: Path) -> None:
        """Partial branch match should return in matches list."""
        from scc_cli.git import find_worktree_by_query

        worktrees = [
            WorktreeInfo(path=str(tmp_path / "main"), branch="main", status=""),
            WorktreeInfo(path=str(tmp_path / "feature-auth"), branch="feature/auth", status=""),
            WorktreeInfo(path=str(tmp_path / "feature-login"), branch="feature/login", status=""),
        ]
        with patch("scc_cli.git._get_worktrees_data", return_value=worktrees):
            exact, matches = find_worktree_by_query(tmp_path, "feature")

        # Should match both feature branches (starts with)
        assert len(matches) == 2

    def test_no_match_returns_empty(self, tmp_path: Path) -> None:
        """No matching query should return empty results."""
        from scc_cli.git import find_worktree_by_query

        worktrees = [
            WorktreeInfo(path=str(tmp_path / "main"), branch="main", status=""),
        ]
        with patch("scc_cli.git._get_worktrees_data", return_value=worktrees):
            exact, matches = find_worktree_by_query(tmp_path, "nonexistent")

        assert exact is None
        assert len(matches) == 0

    def test_directory_name_match(self, tmp_path: Path) -> None:
        """Should match by worktree directory name."""
        from scc_cli.git import find_worktree_by_query

        worktrees = [
            WorktreeInfo(path="/home/user/repos/my-feature", branch="feature/auth", status=""),
        ]
        with patch("scc_cli.git._get_worktrees_data", return_value=worktrees):
            exact, matches = find_worktree_by_query(tmp_path, "my-feature")

        assert exact is not None
        assert exact.path == "/home/user/repos/my-feature"


class TestFindMainWorktree:
    """Test find_main_worktree function."""

    def test_finds_main_branch_worktree(self, tmp_path: Path) -> None:
        """Should find worktree for main/master branch."""
        from scc_cli.git import find_main_worktree

        worktrees = [
            WorktreeInfo(path=str(tmp_path / "feature"), branch="feature/auth", status=""),
            WorktreeInfo(path=str(tmp_path / "main"), branch="main", status=""),
        ]
        with (
            patch("scc_cli.git._get_worktrees_data", return_value=worktrees),
            patch("scc_cli.git.get_default_branch", return_value="main"),
        ):
            result = find_main_worktree(tmp_path)

        assert result is not None
        assert result.branch == "main"

    def test_returns_none_when_no_main_worktree(self, tmp_path: Path) -> None:
        """Should return None when no main branch worktree exists."""
        from scc_cli.git import find_main_worktree

        worktrees = [
            WorktreeInfo(path=str(tmp_path / "feature"), branch="feature/auth", status=""),
        ]
        with (
            patch("scc_cli.git._get_worktrees_data", return_value=worktrees),
            patch("scc_cli.git.get_default_branch", return_value="main"),
        ):
            result = find_main_worktree(tmp_path)

        assert result is None


class TestListBranchesWithoutWorktrees:
    """Test list_branches_without_worktrees function."""

    def test_filters_out_branches_with_worktrees(self, tmp_path: Path) -> None:
        """Should return only branches that don't have worktrees."""
        from scc_cli.git import list_branches_without_worktrees

        worktrees = [
            WorktreeInfo(path=str(tmp_path / "main"), branch="main", status=""),
            WorktreeInfo(path=str(tmp_path / "feature"), branch="feature/auth", status=""),
        ]
        # Simulate git branch -r output with origin/ prefix
        remote_output = "origin/main\norigin/feature/auth\norigin/feature/login\norigin/develop"

        with (
            patch("scc_cli.git._get_worktrees_data", return_value=worktrees),
            patch("scc_cli.git.run_command", return_value=remote_output),
        ):
            result = list_branches_without_worktrees(tmp_path)

        # Result is a list of strings (branch names)
        assert "feature/login" in result
        assert "develop" in result
        assert "main" not in result
        assert "feature/auth" not in result

    def test_empty_when_all_have_worktrees(self, tmp_path: Path) -> None:
        """Should return empty list when all branches have worktrees."""
        from scc_cli.git import list_branches_without_worktrees

        worktrees = [
            WorktreeInfo(path=str(tmp_path / "main"), branch="main", status=""),
        ]
        remote_output = "origin/main"

        with (
            patch("scc_cli.git._get_worktrees_data", return_value=worktrees),
            patch("scc_cli.git.run_command", return_value=remote_output),
        ):
            result = list_branches_without_worktrees(tmp_path)

        assert len(result) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Verbose Worktree List
# ═══════════════════════════════════════════════════════════════════════════════


class TestWorktreeListVerbose:
    """Test worktree list --verbose flag."""

    def test_list_passes_verbose_to_git(self, tmp_path: Path) -> None:
        """list --verbose should pass verbose=True to git.list_worktrees."""
        from scc_cli.cli_worktree import worktree_list_cmd

        with (
            patch("scc_cli.cli_worktree.git.list_worktrees") as mock_list,
            patch("scc_cli.cli_worktree.git.render_worktrees"),
        ):
            mock_list.return_value = [
                WorktreeInfo(path=str(tmp_path), branch="main", status="clean")
            ]
            try:
                worktree_list_cmd(
                    workspace=str(tmp_path),
                    verbose=True,
                    json_output=False,
                    pretty=False,
                )
            except click.exceptions.Exit:
                pass

            mock_list.assert_called_once()
            call_kwargs = mock_list.call_args[1]
            assert call_kwargs.get("verbose") is True


class TestGetWorktreeStatus:
    """Test get_worktree_status function."""

    def test_parses_staged_changes(self, tmp_path: Path) -> None:
        """Should correctly count staged changes."""
        from unittest.mock import MagicMock

        from scc_cli.git import get_worktree_status

        # Git status --porcelain format: XY filename
        # A = staged added, M = staged modified
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "A  newfile.py\nM  changed.py\n"

        with patch("scc_cli.git.subprocess.run", return_value=mock_result):
            staged, modified, untracked, timed_out = get_worktree_status(str(tmp_path))

        assert staged == 2
        assert modified == 0
        assert untracked == 0
        assert timed_out is False

    def test_parses_modified_changes(self, tmp_path: Path) -> None:
        """Should correctly count modified (unstaged) changes."""
        from unittest.mock import MagicMock

        from scc_cli.git import get_worktree_status

        # Space in first column = unstaged, M in second = modified
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = " M modified.py\n"

        with patch("scc_cli.git.subprocess.run", return_value=mock_result):
            staged, modified, untracked, timed_out = get_worktree_status(str(tmp_path))

        assert staged == 0
        assert modified == 1
        assert untracked == 0
        assert timed_out is False

    def test_parses_untracked_files(self, tmp_path: Path) -> None:
        """Should correctly count untracked files."""
        from unittest.mock import MagicMock

        from scc_cli.git import get_worktree_status

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "?? untracked.py\n?? another.py\n"

        with patch("scc_cli.git.subprocess.run", return_value=mock_result):
            staged, modified, untracked, timed_out = get_worktree_status(str(tmp_path))

        assert staged == 0
        assert modified == 0
        assert untracked == 2
        assert timed_out is False

    def test_clean_repo_returns_zeros(self, tmp_path: Path) -> None:
        """Clean repo should return all zeros."""
        from unittest.mock import MagicMock

        from scc_cli.git import get_worktree_status

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        with patch("scc_cli.git.subprocess.run", return_value=mock_result):
            staged, modified, untracked, timed_out = get_worktree_status(str(tmp_path))

        assert staged == 0
        assert modified == 0
        assert untracked == 0
        assert timed_out is False

    def test_timeout_returns_timed_out_flag(self, tmp_path: Path) -> None:
        """Timeout should set timed_out flag to True."""
        import subprocess

        from scc_cli.git import get_worktree_status

        with patch("scc_cli.git.subprocess.run", side_effect=subprocess.TimeoutExpired("git", 5)):
            staged, modified, untracked, timed_out = get_worktree_status(str(tmp_path))

        assert staged == 0
        assert modified == 0
        assert untracked == 0
        assert timed_out is True
