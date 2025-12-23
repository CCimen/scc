"""
Tests for scc init CLI command (Phase 9).

TDD approach: Tests written before implementation.
These tests define the contract for:
- scc init (create .scc.yaml in project root)
- File existence check with --force override
- Git repo detection with warning
- Non-interactive mode support
"""

import json
from pathlib import Path
from unittest.mock import patch

import click
import pytest

# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Init App Structure
# ═══════════════════════════════════════════════════════════════════════════════


class TestInitAppStructure:
    """Test init command Typer structure."""

    def test_init_cmd_exists(self) -> None:
        """init_cmd function should exist."""
        from scc_cli.cli_init import init_cmd

        assert init_cmd is not None
        assert callable(init_cmd)

    def test_init_cmd_registered_in_main_cli(self) -> None:
        """init command should be registered in main CLI."""
        from scc_cli.cli import app

        command_names = [cmd.name for cmd in app.registered_commands]
        assert "init" in command_names


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for File Creation
# ═══════════════════════════════════════════════════════════════════════════════


class TestInitFileCreation:
    """Test .scc.yaml file creation."""

    def test_creates_scc_yaml_in_target_directory(self, tmp_path: Path) -> None:
        """init should create .scc.yaml in target directory."""
        from scc_cli.cli_init import init_cmd

        with patch("scc_cli.cli_init.console"):
            try:
                init_cmd(
                    path=str(tmp_path),
                    force=False,
                    yes=True,
                    json_output=False,
                    pretty=False,
                )
            except click.exceptions.Exit as e:
                assert e.exit_code == 0

        scc_yaml = tmp_path / ".scc.yaml"
        assert scc_yaml.exists()

    def test_creates_valid_yaml_content(self, tmp_path: Path) -> None:
        """init should create valid YAML with documented structure."""
        import yaml

        from scc_cli.cli_init import init_cmd

        with patch("scc_cli.cli_init.console"):
            try:
                init_cmd(
                    path=str(tmp_path),
                    force=False,
                    yes=True,
                    json_output=False,
                    pretty=False,
                )
            except click.exceptions.Exit:
                pass

        scc_yaml = tmp_path / ".scc.yaml"
        content = yaml.safe_load(scc_yaml.read_text())

        # Should have documented sections
        assert content is not None
        # Check for expected top-level keys
        assert "additional_plugins" in content or content.get("additional_plugins") == []

    def test_yaml_contains_helpful_comments(self, tmp_path: Path) -> None:
        """init should create YAML with helpful comments."""
        from scc_cli.cli_init import init_cmd

        with patch("scc_cli.cli_init.console"):
            try:
                init_cmd(
                    path=str(tmp_path),
                    force=False,
                    yes=True,
                    json_output=False,
                    pretty=False,
                )
            except click.exceptions.Exit:
                pass

        scc_yaml = tmp_path / ".scc.yaml"
        content = scc_yaml.read_text()

        # Should have comments explaining the file
        assert "#" in content  # Has comments

    def test_uses_current_directory_as_default(self, tmp_path: Path, monkeypatch) -> None:
        """init without path should use current directory."""
        from scc_cli.cli_init import init_cmd

        monkeypatch.chdir(tmp_path)

        with patch("scc_cli.cli_init.console"):
            try:
                init_cmd(
                    path=None,  # Default to current directory
                    force=False,
                    yes=True,
                    json_output=False,
                    pretty=False,
                )
            except click.exceptions.Exit:
                pass

        scc_yaml = tmp_path / ".scc.yaml"
        assert scc_yaml.exists()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for File Existence Check
# ═══════════════════════════════════════════════════════════════════════════════


class TestInitFileExistenceCheck:
    """Test file existence detection and --force flag."""

    def test_fails_if_scc_yaml_exists(self, tmp_path: Path) -> None:
        """init should fail if .scc.yaml already exists without --force."""
        from scc_cli.cli_init import init_cmd

        # Create existing file
        existing = tmp_path / ".scc.yaml"
        existing.write_text("existing: content\n")

        with patch("scc_cli.cli_init.console"):
            with pytest.raises(click.exceptions.Exit) as exc_info:
                init_cmd(
                    path=str(tmp_path),
                    force=False,
                    yes=True,
                    json_output=False,
                    pretty=False,
                )
            assert exc_info.value.exit_code != 0

    def test_force_overwrites_existing_file(self, tmp_path: Path) -> None:
        """init --force should overwrite existing .scc.yaml."""
        from scc_cli.cli_init import init_cmd

        # Create existing file
        existing = tmp_path / ".scc.yaml"
        existing.write_text("existing: content\n")
        original_content = existing.read_text()

        with patch("scc_cli.cli_init.console"):
            try:
                init_cmd(
                    path=str(tmp_path),
                    force=True,
                    yes=True,
                    json_output=False,
                    pretty=False,
                )
            except click.exceptions.Exit:
                pass

        # Content should be different (overwritten)
        assert existing.read_text() != original_content


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Git Repo Detection
# ═══════════════════════════════════════════════════════════════════════════════


class TestInitGitRepoDetection:
    """Test git repository detection and warnings."""

    def test_detects_git_repo(self, tmp_path: Path) -> None:
        """init should detect if target is a git repository."""
        from scc_cli.cli_init import is_git_repo

        # Create a git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        assert is_git_repo(tmp_path) is True

    def test_detects_non_git_directory(self, tmp_path: Path) -> None:
        """init should detect non-git directories."""
        from scc_cli.cli_init import is_git_repo

        # No .git directory
        assert is_git_repo(tmp_path) is False

    def test_warns_if_not_git_repo(self, tmp_path: Path, capsys) -> None:
        """init should warn if target is not a git repository."""
        from scc_cli.cli_init import init_cmd

        # Don't create .git directory

        with patch("scc_cli.cli_init.console") as mock_console:
            try:
                init_cmd(
                    path=str(tmp_path),
                    force=False,
                    yes=True,
                    json_output=False,
                    pretty=False,
                )
            except click.exceptions.Exit:
                pass

            # Should have printed a warning
            calls = [str(c) for c in mock_console.print.call_args_list]
            warning_printed = any(
                "git" in str(c).lower() or "warning" in str(c).lower() for c in calls
            )
            assert warning_printed


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Non-Interactive Mode
# ═══════════════════════════════════════════════════════════════════════════════


class TestInitNonInteractiveMode:
    """Test --non-interactive flag."""

    def test_non_interactive_uses_defaults(self, tmp_path: Path) -> None:
        """init --non-interactive should use defaults without prompts."""
        from scc_cli.cli_init import init_cmd

        with patch("scc_cli.cli_init.console"):
            try:
                init_cmd(
                    path=str(tmp_path),
                    force=False,
                    yes=True,
                    json_output=False,
                    pretty=False,
                )
            except click.exceptions.Exit:
                pass

        # Should complete successfully without prompts
        assert (tmp_path / ".scc.yaml").exists()

    def test_interactive_mode_available(self, tmp_path: Path) -> None:
        """init without --yes should support interactive mode."""
        # This test verifies the function signature supports interactive/non-interactive mode
        import inspect

        from scc_cli.cli_init import init_cmd

        sig = inspect.signature(init_cmd)
        assert "yes" in sig.parameters


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for JSON Output
# ═══════════════════════════════════════════════════════════════════════════════


class TestInitJsonOutput:
    """Test --json output mode."""

    def test_json_output_valid_envelope(self, tmp_path: Path, capsys) -> None:
        """init --json should output valid JSON envelope."""
        from scc_cli.cli_init import init_cmd

        try:
            init_cmd(
                path=str(tmp_path),
                force=False,
                yes=True,
                json_output=True,
                pretty=False,
            )
        except click.exceptions.Exit:
            pass

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["kind"] == "InitResult"
        assert output["apiVersion"] == "scc.cli/v1"
        assert output["status"]["ok"] is True

    def test_json_output_includes_file_path(self, tmp_path: Path, capsys) -> None:
        """init --json should include created file path."""
        from scc_cli.cli_init import init_cmd

        try:
            init_cmd(
                path=str(tmp_path),
                force=False,
                yes=True,
                json_output=True,
                pretty=False,
            )
        except click.exceptions.Exit:
            pass

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "file_path" in output["data"]
        assert ".scc.yaml" in output["data"]["file_path"]


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Error Handling
# ═══════════════════════════════════════════════════════════════════════════════


class TestInitErrorHandling:
    """Test error handling scenarios."""

    def test_fails_on_nonexistent_path(self) -> None:
        """init should fail if target path doesn't exist."""
        from scc_cli.cli_init import init_cmd

        with patch("scc_cli.cli_init.console"):
            with pytest.raises(click.exceptions.Exit) as exc_info:
                init_cmd(
                    path="/nonexistent/path/to/project",
                    force=False,
                    yes=True,
                    json_output=False,
                    pretty=False,
                )
            assert exc_info.value.exit_code != 0

    def test_fails_if_path_is_file(self, tmp_path: Path) -> None:
        """init should fail if target path is a file, not directory."""
        from scc_cli.cli_init import init_cmd

        # Create a file instead of directory
        file_path = tmp_path / "not_a_dir"
        file_path.write_text("I'm a file")

        with patch("scc_cli.cli_init.console"):
            with pytest.raises(click.exceptions.Exit) as exc_info:
                init_cmd(
                    path=str(file_path),
                    force=False,
                    yes=True,
                    json_output=False,
                    pretty=False,
                )
            assert exc_info.value.exit_code != 0


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Pure Functions
# ═══════════════════════════════════════════════════════════════════════════════


class TestPureFunctions:
    """Test pure functions for testability."""

    def test_build_init_data_success(self) -> None:
        """build_init_data should return correct structure for success."""
        from scc_cli.cli_init import build_init_data

        result = build_init_data(
            file_path="/path/to/.scc.yaml",
            created=True,
            overwritten=False,
            is_git_repo=True,
        )

        assert result["file_path"] == "/path/to/.scc.yaml"
        assert result["created"] is True
        assert result["overwritten"] is False
        assert result["is_git_repo"] is True

    def test_build_init_data_overwrite(self) -> None:
        """build_init_data should indicate overwrite."""
        from scc_cli.cli_init import build_init_data

        result = build_init_data(
            file_path="/path/to/.scc.yaml",
            created=True,
            overwritten=True,
            is_git_repo=True,
        )

        assert result["overwritten"] is True

    def test_generate_template_content(self) -> None:
        """generate_template_content should return valid YAML template."""
        from scc_cli.cli_init import generate_template_content

        content = generate_template_content()

        # Should be valid YAML
        import yaml

        parsed = yaml.safe_load(content)
        assert parsed is not None or content.strip().startswith("#")

        # Should have comments
        assert "#" in content
