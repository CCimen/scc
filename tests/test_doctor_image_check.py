"""Tests for the provider image doctor check."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from scc_cli.doctor.checks.environment import check_provider_image


class TestCheckProviderImage:
    """Tests for check_provider_image()."""

    @patch("scc_cli.doctor.checks.environment.subprocess.run")
    def test_image_found_claude(self, mock_run: MagicMock) -> None:
        """Image present locally → passed=True."""
        mock_run.return_value = MagicMock(returncode=0)

        with patch("scc_cli.config.get_selected_provider", return_value="claude"):
            result = check_provider_image()

        assert result.passed is True
        assert result.name == "Provider Image"
        assert "scc-agent-claude:latest" in result.message

    @patch("scc_cli.doctor.checks.environment.subprocess.run")
    def test_image_found_codex(self, mock_run: MagicMock) -> None:
        """Codex provider image present → passed=True."""
        mock_run.return_value = MagicMock(returncode=0)

        with patch("scc_cli.config.get_selected_provider", return_value="codex"):
            result = check_provider_image()

        assert result.passed is True
        assert "scc-agent-codex:latest" in result.message

    @patch("scc_cli.doctor.checks.environment.subprocess.run")
    def test_image_not_found_claude(self, mock_run: MagicMock) -> None:
        """Image missing → passed=False with correct fix_commands."""
        mock_run.return_value = MagicMock(returncode=1)

        with patch("scc_cli.config.get_selected_provider", return_value="claude"):
            result = check_provider_image()

        assert result.passed is False
        assert result.fix_commands is not None
        assert len(result.fix_commands) == 1
        assert result.fix_commands[0] == "docker build -t scc-agent-claude:latest images/scc-agent-claude/"
        assert result.fix_hint == "Build the claude agent image"
        assert result.severity == "warning"

    @patch("scc_cli.doctor.checks.environment.subprocess.run")
    def test_image_not_found_codex(self, mock_run: MagicMock) -> None:
        """Codex image missing → fix_commands uses codex paths."""
        mock_run.return_value = MagicMock(returncode=1)

        with patch("scc_cli.config.get_selected_provider", return_value="codex"):
            result = check_provider_image()

        assert result.passed is False
        assert result.fix_commands is not None
        assert result.fix_commands[0] == "docker build -t scc-agent-codex:latest images/scc-agent-codex/"
        assert result.fix_hint == "Build the codex agent image"

    @patch("scc_cli.doctor.checks.environment.subprocess.run")
    def test_unknown_provider_falls_back_to_claude(self, mock_run: MagicMock) -> None:
        """Unknown provider_id → falls back to claude image ref."""
        mock_run.return_value = MagicMock(returncode=0)

        with patch("scc_cli.config.get_selected_provider", return_value="unknown_provider"):
            result = check_provider_image()

        assert result.passed is True
        assert "scc-agent-claude:latest" in result.message

    @patch("scc_cli.doctor.checks.environment.subprocess.run")
    def test_no_provider_selected_defaults_to_claude(self, mock_run: MagicMock) -> None:
        """No provider selected (None) → defaults to claude."""
        mock_run.return_value = MagicMock(returncode=0)

        with patch("scc_cli.config.get_selected_provider", return_value=None):
            result = check_provider_image()

        assert result.passed is True
        assert "scc-agent-claude:latest" in result.message

    @patch("scc_cli.doctor.checks.environment.subprocess.run")
    def test_subprocess_timeout(self, mock_run: MagicMock) -> None:
        """Subprocess timeout → graceful failure."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="docker", timeout=10)

        with patch("scc_cli.config.get_selected_provider", return_value="claude"):
            result = check_provider_image()

        assert result.passed is False
        assert "Could not check provider image" in result.message
        assert result.severity == "warning"

    @patch("scc_cli.doctor.checks.environment.subprocess.run")
    def test_docker_not_found(self, mock_run: MagicMock) -> None:
        """Docker binary missing → FileNotFoundError → graceful failure."""
        mock_run.side_effect = FileNotFoundError("docker not found")

        with patch("scc_cli.config.get_selected_provider", return_value="claude"):
            result = check_provider_image()

        assert result.passed is False
        assert "Could not check provider image" in result.message
        assert result.fix_hint == "Ensure Docker is installed and reachable"

    def test_config_module_import_failure(self) -> None:
        """If config import fails, falls back to claude."""
        with (
            patch(
                "scc_cli.doctor.checks.environment.subprocess.run",
                return_value=MagicMock(returncode=0),
            ),
            patch(
                "scc_cli.doctor.checks.environment.config_module",
                create=True,
                side_effect=ImportError("no config"),
            ),
        ):
            # The function does a deferred import, so we patch at the import site
            with patch.dict("sys.modules", {"scc_cli.config": None}):
                # When the import itself raises, provider defaults to "claude"
                result = check_provider_image()

        assert result.passed is True
        assert "scc-agent-claude:latest" in result.message


class TestCheckProviderImageInDoctor:
    """Integration: check_provider_image wired into run_doctor."""

    @patch("scc_cli.doctor.checks.environment.subprocess.run")
    @patch("scc_cli.config.get_selected_provider", return_value="claude")
    def test_doctor_includes_provider_image_check(
        self,
        mock_provider: MagicMock,
        mock_subprocess: MagicMock,
    ) -> None:
        """run_doctor includes Provider Image when docker_ok."""
        # Make docker checks pass
        mock_subprocess.return_value = MagicMock(returncode=0)

        with (
            patch("scc_cli.doctor.checks.environment.check_git") as mock_git,
            patch("scc_cli.doctor.core.check_git") as mock_core_git,
            patch("scc_cli.doctor.core.check_docker") as mock_docker,
            patch("scc_cli.doctor.core.check_docker_running") as mock_daemon,
            patch("scc_cli.doctor.core.check_docker_sandbox") as mock_sandbox,
            patch("scc_cli.doctor.core.check_runtime_backend") as mock_runtime,
            patch("scc_cli.doctor.core.check_provider_image") as mock_image,
            patch("scc_cli.doctor.core.check_wsl2") as mock_wsl,
            patch("scc_cli.doctor.core.check_config_directory") as mock_config,
            patch("scc_cli.doctor.core.check_user_config_valid") as mock_user_cfg,
            patch("scc_cli.doctor.core.check_safety_policy") as mock_safety,
        ):
            from scc_cli.doctor.types import CheckResult

            passed_result = CheckResult(name="test", passed=True, message="ok")
            mock_core_git.return_value = CheckResult(
                name="Git", passed=True, message="ok", version="2.40"
            )
            mock_docker.return_value = CheckResult(
                name="Docker", passed=True, message="ok", version="24.0"
            )
            mock_daemon.return_value = CheckResult(
                name="Docker Daemon", passed=True, message="ok"
            )
            mock_sandbox.return_value = CheckResult(
                name="Sandbox Backend", passed=True, message="ok"
            )
            mock_runtime.return_value = passed_result
            mock_image.return_value = CheckResult(
                name="Provider Image", passed=True, message="scc-agent-claude:latest found"
            )
            mock_wsl.return_value = (passed_result, False)
            mock_config.return_value = passed_result
            mock_user_cfg.return_value = passed_result
            mock_safety.return_value = passed_result

            from scc_cli.doctor.core import run_doctor

            doctor_result = run_doctor()

        check_names = [c.name for c in doctor_result.checks]
        assert "Provider Image" in check_names
        mock_image.assert_called_once()
