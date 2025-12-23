"""Tests for scc prune command.

TDD tests written BEFORE implementation to define expected behavior:
- Interactive confirmation by default (Docker-style UX)
- --yes / -y / -f flag to skip confirmation (for scripts/CI)
- --dry-run flag to only preview without prompting
- Only removes STOPPED containers (by image, same as stop command)
- Never touches running containers

Design principle: "Narrow and boring" - one safe thing done well.
"""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from scc_cli.cli import app

runner = CliRunner()


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def stopped_container():
    """A stopped SCC container."""
    container = MagicMock()
    container.id = "abc123def456"
    container.name = "scc-project-feature"
    container.status = "Exited (0) 2 hours ago"
    container.workspace = "/home/user/project"
    container.profile = "platform"
    container.branch = "feature-branch"
    return container


@pytest.fixture
def running_container():
    """A running SCC container."""
    container = MagicMock()
    container.id = "running789xyz"
    container.name = "scc-project-main"
    container.status = "Up 30 minutes"
    container.workspace = "/home/user/project"
    container.profile = "platform"
    container.branch = "main"
    return container


@pytest.fixture
def multiple_stopped_containers():
    """Multiple stopped containers for batch removal tests."""
    containers = []
    for i in range(3):
        c = MagicMock()
        c.id = f"stopped{i}abc"
        c.name = f"scc-project-feature{i}"
        c.status = f"Exited (0) {i + 1} hours ago"
        c.workspace = f"/home/user/project{i}"
        c.profile = "platform"
        c.branch = f"feature-{i}"
        containers.append(c)
    return containers


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for --dry-run flag behavior
# ═══════════════════════════════════════════════════════════════════════════════


class TestPruneDryRunFlag:
    """Prune --dry-run should show what would be removed without prompting."""

    def test_prune_dry_run_shows_what_would_be_removed(self, stopped_container):
        """--dry-run should list containers that would be removed."""
        with patch(
            "scc_cli.cli_worktree.docker._list_all_sandbox_containers",
            return_value=[stopped_container],
        ):
            result = runner.invoke(app, ["prune", "--dry-run"])

        assert result.exit_code == 0
        # Should mention it's a dry run
        assert "dry run" in result.output.lower()
        # Should show container info
        assert stopped_container.name in result.output or "1" in result.output

    def test_prune_dry_run_does_not_remove(self, stopped_container):
        """--dry-run should NOT call remove_container."""
        with (
            patch(
                "scc_cli.cli_worktree.docker._list_all_sandbox_containers",
                return_value=[stopped_container],
            ),
            patch("scc_cli.cli_worktree.docker.remove_container") as mock_remove,
        ):
            result = runner.invoke(app, ["prune", "--dry-run"])

        assert result.exit_code == 0
        mock_remove.assert_not_called()

    def test_prune_dry_run_does_not_prompt(self, stopped_container):
        """--dry-run should not prompt for confirmation."""
        with patch(
            "scc_cli.cli_worktree.docker._list_all_sandbox_containers",
            return_value=[stopped_container],
        ):
            # No input provided - would fail if it prompted
            result = runner.invoke(app, ["prune", "--dry-run"])

        assert result.exit_code == 0
        # Should show "Dry run complete" message
        assert "dry run" in result.output.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for interactive confirmation (default behavior)
# ═══════════════════════════════════════════════════════════════════════════════


class TestPruneInteractiveConfirmation:
    """Prune should prompt for confirmation by default (Docker-style)."""

    def test_prune_prompts_for_confirmation(self, stopped_container):
        """Default prune should show containers and prompt."""
        with (
            patch(
                "scc_cli.cli_worktree.docker._list_all_sandbox_containers",
                return_value=[stopped_container],
            ),
            patch("scc_cli.cli_worktree.docker.remove_container", return_value=True),
            patch("scc_cli.cli_helpers.is_interactive", return_value=True),
        ):
            # Provide 'y' input to confirm
            result = runner.invoke(app, ["prune"], input="y\n")

        assert result.exit_code == 0
        # Should show container name
        assert stopped_container.name in result.output
        # Should ask for confirmation
        assert "remove" in result.output.lower()

    def test_prune_aborts_on_no(self, stopped_container):
        """Answering 'n' should abort without removing."""
        with (
            patch(
                "scc_cli.cli_worktree.docker._list_all_sandbox_containers",
                return_value=[stopped_container],
            ),
            patch("scc_cli.cli_worktree.docker.remove_container") as mock_remove,
            patch("scc_cli.cli_helpers.is_interactive", return_value=True),
        ):
            result = runner.invoke(app, ["prune"], input="n\n")

        assert result.exit_code == 0
        # Should show aborted message
        assert "aborted" in result.output.lower()
        # Should NOT remove
        mock_remove.assert_not_called()

    def test_prune_removes_on_yes(self, stopped_container):
        """Answering 'y' should remove containers."""
        with (
            patch(
                "scc_cli.cli_worktree.docker._list_all_sandbox_containers",
                return_value=[stopped_container],
            ),
            patch("scc_cli.cli_worktree.docker.remove_container", return_value=True) as mock_remove,
            patch("scc_cli.cli_helpers.is_interactive", return_value=True),
        ):
            result = runner.invoke(app, ["prune"], input="y\n")

        assert result.exit_code == 0
        mock_remove.assert_called_once_with(stopped_container.name)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for --yes flag (actual removal)
# ═══════════════════════════════════════════════════════════════════════════════


class TestPruneWithYesFlag:
    """Prune --yes should actually remove stopped containers."""

    def test_prune_yes_removes_stopped_containers(self, stopped_container):
        """--yes flag should actually remove containers."""
        with (
            patch(
                "scc_cli.cli_worktree.docker._list_all_sandbox_containers",
                return_value=[stopped_container],
            ),
            patch("scc_cli.cli_worktree.docker.remove_container", return_value=True) as mock_remove,
        ):
            result = runner.invoke(app, ["prune", "--yes"])

        assert result.exit_code == 0
        mock_remove.assert_called_once_with(stopped_container.name)

    def test_prune_short_y_flag_works(self, stopped_container):
        """-y short flag should work like --yes."""
        with (
            patch(
                "scc_cli.cli_worktree.docker._list_all_sandbox_containers",
                return_value=[stopped_container],
            ),
            patch("scc_cli.cli_worktree.docker.remove_container", return_value=True) as mock_remove,
        ):
            result = runner.invoke(app, ["prune", "-y"])

        assert result.exit_code == 0
        mock_remove.assert_called_once()

    def test_prune_yes_shows_success_count(self, multiple_stopped_containers):
        """Should show count of removed containers."""
        with (
            patch(
                "scc_cli.cli_worktree.docker._list_all_sandbox_containers",
                return_value=multiple_stopped_containers,
            ),
            patch("scc_cli.cli_worktree.docker.remove_container", return_value=True),
        ):
            result = runner.invoke(app, ["prune", "--yes"])

        assert result.exit_code == 0
        # Should mention count (3 containers)
        assert "3" in result.output or "removed" in result.output.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for stopped-only filtering
# ═══════════════════════════════════════════════════════════════════════════════


class TestPruneOnlyStoppedContainers:
    """Prune should ONLY target stopped containers, never running ones."""

    def test_prune_ignores_running_containers(self, running_container, stopped_container):
        """Running containers should be excluded from pruning."""
        with (
            patch(
                "scc_cli.cli_worktree.docker._list_all_sandbox_containers",
                return_value=[running_container, stopped_container],
            ),
            patch("scc_cli.cli_worktree.docker.remove_container", return_value=True) as mock_remove,
        ):
            result = runner.invoke(app, ["prune", "--yes"])

        assert result.exit_code == 0
        # Should only remove the stopped one
        mock_remove.assert_called_once_with(stopped_container.name)

    def test_prune_dry_run_only_lists_stopped(self, running_container, stopped_container):
        """--dry-run should only list stopped containers."""
        with patch(
            "scc_cli.cli_worktree.docker._list_all_sandbox_containers",
            return_value=[running_container, stopped_container],
        ):
            result = runner.invoke(app, ["prune", "--dry-run"])

        assert result.exit_code == 0
        # Should mention 1 container (only stopped), not 2
        assert stopped_container.name in result.output or "1" in result.output
        # Running container should not be listed for removal

    def test_prune_all_running_shows_nothing_to_remove(self, running_container):
        """If all containers are running, should indicate nothing to prune."""
        with (
            patch(
                "scc_cli.cli_worktree.docker._list_all_sandbox_containers",
                return_value=[running_container],
            ),
            patch("scc_cli.cli_helpers.is_interactive", return_value=True),
        ):
            result = runner.invoke(app, ["prune"])

        assert result.exit_code == 0
        # Should indicate no stopped containers
        assert (
            "no" in result.output.lower()
            or "0" in result.output
            or "nothing" in result.output.lower()
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for empty state handling
# ═══════════════════════════════════════════════════════════════════════════════


class TestPruneEmptyState:
    """Prune should handle empty states gracefully."""

    def test_prune_no_containers_shows_message(self):
        """Should show message when no SCC containers exist."""
        with (
            patch("scc_cli.cli_worktree.docker._list_all_sandbox_containers", return_value=[]),
            patch("scc_cli.cli_helpers.is_interactive", return_value=True),
        ):
            result = runner.invoke(app, ["prune"])

        assert result.exit_code == 0
        # Should indicate nothing to prune
        assert (
            "no" in result.output.lower()
            or "nothing" in result.output.lower()
            or "0" in result.output
        )

    def test_prune_yes_no_containers_shows_message(self):
        """--yes with no containers should show message, not error."""
        with patch("scc_cli.cli_worktree.docker._list_all_sandbox_containers", return_value=[]):
            result = runner.invoke(app, ["prune", "--yes"])

        assert result.exit_code == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for error handling
# ═══════════════════════════════════════════════════════════════════════════════


class TestPruneErrorHandling:
    """Prune should handle errors gracefully."""

    def test_prune_handles_removal_failure(self, stopped_container):
        """Should handle failed container removal gracefully."""
        with (
            patch(
                "scc_cli.cli_worktree.docker._list_all_sandbox_containers",
                return_value=[stopped_container],
            ),
            patch("scc_cli.cli_worktree.docker.remove_container", return_value=False),
        ):
            result = runner.invoke(app, ["prune", "--yes"])

        # Should not crash, may show warning
        assert result.exit_code in (0, 1)

    def test_prune_reports_partial_success(self, multiple_stopped_containers):
        """Should report both successes and failures."""
        # First two succeed, third fails
        with (
            patch(
                "scc_cli.cli_worktree.docker._list_all_sandbox_containers",
                return_value=multiple_stopped_containers,
            ),
            patch(
                "scc_cli.cli_worktree.docker.remove_container",
                side_effect=[True, True, False],
            ),
        ):
            result = runner.invoke(app, ["prune", "--yes"])

        # Should complete (may warn about failures)
        assert result.exit_code in (0, 1)
        # Should mention some removal (2 succeeded)
        assert "2" in result.output or "removed" in result.output.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for status detection
# ═══════════════════════════════════════════════════════════════════════════════


class TestPruneStatusDetection:
    """Prune should correctly identify stopped vs running containers."""

    @pytest.mark.parametrize(
        "status,is_stopped",
        [
            ("Exited (0) 2 hours ago", True),
            ("Exited (1) 30 minutes ago", True),
            ("Exited (137) 5 seconds ago", True),
            ("Up 2 hours", False),
            ("Up 30 seconds", False),
            ("Up 2 hours (healthy)", False),
            ("Created", True),  # Created but never started
            ("Dead", True),
        ],
    )
    def test_container_status_classification(self, status, is_stopped):
        """Various container statuses should be classified correctly."""
        container = MagicMock()
        container.id = "test123"
        container.name = "scc-test"
        container.status = status
        container.workspace = "/test"
        container.profile = "test"
        container.branch = "main"

        with (
            patch(
                "scc_cli.cli_worktree.docker._list_all_sandbox_containers",
                return_value=[container],
            ),
            patch("scc_cli.cli_worktree.docker.remove_container", return_value=True) as mock_remove,
        ):
            runner.invoke(app, ["prune", "--yes"])

        if is_stopped:
            # Should try to remove stopped containers
            mock_remove.assert_called_once()
        else:
            # Should NOT try to remove running containers
            mock_remove.assert_not_called()
