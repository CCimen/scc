"""Tests for T02: doctor provider wiring, CLI flag, category assignment, and grouped output.

Covers:
- run_doctor() threads provider_id to check_provider_image and check_provider_auth
- run_doctor() assigns categories to all checks
- doctor_cmd --provider validates against KNOWN_PROVIDERS
- doctor_cmd --provider unknown exits with error
- build_doctor_json_data includes category field
- render_doctor_results groups by category (check table row order)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from scc_cli.core.enums import SeverityLevel
from scc_cli.doctor.core import _CATEGORY_MAP, _assign_category, run_doctor
from scc_cli.doctor.render import _sort_checks_by_category, render_doctor_results
from scc_cli.doctor.serialization import build_doctor_json_data
from scc_cli.doctor.types import CheckResult, DoctorResult

# ---------------------------------------------------------------------------
# Category assignment
# ---------------------------------------------------------------------------


class TestCategoryAssignment:
    """Verify _assign_category populates the category field correctly."""

    def test_git_gets_backend(self) -> None:
        check = CheckResult(name="Git", passed=True, message="ok")
        _assign_category(check)
        assert check.category == "backend"

    def test_docker_gets_backend(self) -> None:
        check = CheckResult(name="Docker", passed=True, message="ok")
        _assign_category(check)
        assert check.category == "backend"

    def test_provider_image_gets_provider(self) -> None:
        check = CheckResult(name="Provider Image", passed=True, message="ok")
        _assign_category(check)
        assert check.category == "provider"

    def test_provider_auth_gets_provider(self) -> None:
        check = CheckResult(name="Provider Auth", passed=True, message="ok")
        _assign_category(check)
        assert check.category == "provider"

    def test_config_directory_gets_config(self) -> None:
        check = CheckResult(name="Config Directory", passed=True, message="ok")
        _assign_category(check)
        assert check.category == "config"

    def test_safety_policy_gets_config(self) -> None:
        check = CheckResult(name="Safety Policy", passed=True, message="ok")
        _assign_category(check)
        assert check.category == "config"

    def test_worktree_health_gets_worktree(self) -> None:
        check = CheckResult(name="Worktree Health", passed=True, message="ok")
        _assign_category(check)
        assert check.category == "worktree"

    def test_unknown_check_stays_general(self) -> None:
        check = CheckResult(name="Custom Thing", passed=True, message="ok")
        _assign_category(check)
        assert check.category == "general"

    def test_preexisting_category_preserved(self) -> None:
        """If the check function already set a non-default category, keep it."""
        check = CheckResult(name="Git", passed=True, message="ok", category="provider")
        _assign_category(check)
        assert check.category == "provider"

    def test_all_mapped_names_are_present(self) -> None:
        """Ensure every mapped name resolves to a known category."""
        known_categories = {"backend", "provider", "config", "worktree", "general"}
        for name, cat in _CATEGORY_MAP.items():
            assert cat in known_categories, f"{name!r} maps to unknown category {cat!r}"


# ---------------------------------------------------------------------------
# run_doctor threads provider_id
# ---------------------------------------------------------------------------


class TestRunDoctorProviderThreading:
    """Verify run_doctor passes provider_id to provider checks."""

    @patch("scc_cli.doctor.core.check_safety_policy")
    @patch("scc_cli.doctor.core.check_user_config_valid")
    @patch("scc_cli.doctor.core.check_config_directory")
    @patch("scc_cli.doctor.core.check_wsl2")
    @patch("scc_cli.doctor.core.check_provider_auth")
    @patch("scc_cli.doctor.core.check_provider_image")
    @patch("scc_cli.doctor.core.check_runtime_backend")
    @patch("scc_cli.doctor.core.check_docker_sandbox")
    @patch("scc_cli.doctor.core.check_docker_running")
    @patch("scc_cli.doctor.core.check_docker")
    @patch("scc_cli.doctor.core.check_git")
    def test_provider_id_passed_to_image_check(
        self,
        mock_git: MagicMock,
        mock_docker: MagicMock,
        mock_docker_running: MagicMock,
        mock_sandbox: MagicMock,
        mock_runtime: MagicMock,
        mock_image: MagicMock,
        mock_auth: MagicMock,
        mock_wsl2: MagicMock,
        mock_config_dir: MagicMock,
        mock_user_config: MagicMock,
        mock_safety: MagicMock,
    ) -> None:
        """run_doctor(provider_id='codex') threads it to check_provider_image."""
        ok = CheckResult(name="ok", passed=True, message="ok")
        mock_git.return_value = ok
        mock_docker.return_value = CheckResult(name="Docker", passed=True, message="ok", version="24.0")
        mock_docker_running.return_value = ok
        mock_sandbox.return_value = CheckResult(name="Sandbox", passed=True, message="ok")
        mock_runtime.return_value = ok
        mock_image.return_value = ok
        mock_auth.return_value = ok
        mock_wsl2.return_value = (ok, False)
        mock_config_dir.return_value = ok
        mock_user_config.return_value = ok
        mock_safety.return_value = ok

        run_doctor(provider_id="codex")

        mock_image.assert_called_once_with(provider_id="codex")

    @patch("scc_cli.doctor.core.check_safety_policy")
    @patch("scc_cli.doctor.core.check_user_config_valid")
    @patch("scc_cli.doctor.core.check_config_directory")
    @patch("scc_cli.doctor.core.check_wsl2")
    @patch("scc_cli.doctor.core.check_provider_auth")
    @patch("scc_cli.doctor.core.check_provider_image")
    @patch("scc_cli.doctor.core.check_runtime_backend")
    @patch("scc_cli.doctor.core.check_docker_sandbox")
    @patch("scc_cli.doctor.core.check_docker_running")
    @patch("scc_cli.doctor.core.check_docker")
    @patch("scc_cli.doctor.core.check_git")
    def test_provider_id_passed_to_auth_check(
        self,
        mock_git: MagicMock,
        mock_docker: MagicMock,
        mock_docker_running: MagicMock,
        mock_sandbox: MagicMock,
        mock_runtime: MagicMock,
        mock_image: MagicMock,
        mock_auth: MagicMock,
        mock_wsl2: MagicMock,
        mock_config_dir: MagicMock,
        mock_user_config: MagicMock,
        mock_safety: MagicMock,
    ) -> None:
        """run_doctor(provider_id='codex') threads it to check_provider_auth."""
        ok = CheckResult(name="ok", passed=True, message="ok")
        mock_git.return_value = ok
        mock_docker.return_value = CheckResult(name="Docker", passed=True, message="ok", version="24.0")
        mock_docker_running.return_value = ok
        mock_sandbox.return_value = CheckResult(name="Sandbox", passed=True, message="ok")
        mock_runtime.return_value = ok
        mock_image.return_value = ok
        mock_auth.return_value = ok
        mock_wsl2.return_value = (ok, False)
        mock_config_dir.return_value = ok
        mock_user_config.return_value = ok
        mock_safety.return_value = ok

        run_doctor(provider_id="codex")

        mock_auth.assert_called_once_with(provider_id="codex")

    @patch("scc_cli.doctor.core.check_safety_policy")
    @patch("scc_cli.doctor.core.check_user_config_valid")
    @patch("scc_cli.doctor.core.check_config_directory")
    @patch("scc_cli.doctor.core.check_wsl2")
    @patch("scc_cli.doctor.core.check_provider_auth")
    @patch("scc_cli.doctor.core.check_provider_image")
    @patch("scc_cli.doctor.core.check_runtime_backend")
    @patch("scc_cli.doctor.core.check_docker_sandbox")
    @patch("scc_cli.doctor.core.check_docker_running")
    @patch("scc_cli.doctor.core.check_docker")
    @patch("scc_cli.doctor.core.check_git")
    def test_categories_assigned_after_run(
        self,
        mock_git: MagicMock,
        mock_docker: MagicMock,
        mock_docker_running: MagicMock,
        mock_sandbox: MagicMock,
        mock_runtime: MagicMock,
        mock_image: MagicMock,
        mock_auth: MagicMock,
        mock_wsl2: MagicMock,
        mock_config_dir: MagicMock,
        mock_user_config: MagicMock,
        mock_safety: MagicMock,
    ) -> None:
        """All checks have categories assigned after run_doctor completes."""
        mock_git.return_value = CheckResult(name="Git", passed=True, message="ok")
        mock_docker.return_value = CheckResult(name="Docker", passed=True, message="ok", version="24.0")
        mock_docker_running.return_value = CheckResult(name="Docker Daemon", passed=True, message="ok")
        mock_sandbox.return_value = CheckResult(name="Sandbox Backend", passed=True, message="ok")
        mock_runtime.return_value = CheckResult(name="Runtime Backend", passed=True, message="ok")
        mock_image.return_value = CheckResult(name="Provider Image", passed=True, message="ok")
        mock_auth.return_value = CheckResult(name="Provider Auth", passed=True, message="ok")
        mock_wsl2.return_value = (CheckResult(name="WSL2", passed=True, message="ok"), False)
        mock_config_dir.return_value = CheckResult(name="Config Directory", passed=True, message="ok")
        mock_user_config.return_value = CheckResult(name="User Config", passed=True, message="ok")
        mock_safety.return_value = CheckResult(name="Safety Policy", passed=True, message="ok")

        result = run_doctor()

        for check in result.checks:
            assert check.category != "", f"Check {check.name!r} has empty category"
            # Named checks should have a mapped category, not 'general' (except WSL2)
            if check.name in _CATEGORY_MAP:
                assert check.category == _CATEGORY_MAP[check.name]

    @patch("scc_cli.doctor.core.check_safety_policy")
    @patch("scc_cli.doctor.core.check_user_config_valid")
    @patch("scc_cli.doctor.core.check_config_directory")
    @patch("scc_cli.doctor.core.check_wsl2")
    @patch("scc_cli.doctor.core.check_provider_auth")
    @patch("scc_cli.doctor.core.check_provider_image")
    @patch("scc_cli.doctor.core.check_runtime_backend")
    @patch("scc_cli.doctor.core.check_docker_sandbox")
    @patch("scc_cli.doctor.core.check_docker_running")
    @patch("scc_cli.doctor.core.check_docker")
    @patch("scc_cli.doctor.core.check_git")
    def test_run_doctor_without_provider_checks_both_known_providers(
        self,
        mock_git: MagicMock,
        mock_docker: MagicMock,
        mock_docker_running: MagicMock,
        mock_sandbox: MagicMock,
        mock_runtime: MagicMock,
        mock_image: MagicMock,
        mock_auth: MagicMock,
        mock_wsl2: MagicMock,
        mock_config_dir: MagicMock,
        mock_user_config: MagicMock,
        mock_safety: MagicMock,
    ) -> None:
        ok = CheckResult(name="ok", passed=True, message="ok")
        mock_git.return_value = ok
        mock_docker.return_value = CheckResult(name="Docker", passed=True, message="ok", version="24.0")
        mock_docker_running.return_value = ok
        mock_sandbox.return_value = ok
        mock_runtime.return_value = ok
        mock_image.side_effect = [
            CheckResult(name="Provider Image", passed=True, message="ok", category="provider"),
            CheckResult(name="Provider Image", passed=True, message="ok", category="provider"),
        ]
        mock_auth.side_effect = [
            CheckResult(name="Provider Auth", passed=True, message="ok", category="provider"),
            CheckResult(name="Provider Auth", passed=True, message="ok", category="provider"),
        ]
        mock_wsl2.return_value = (ok, False)
        mock_config_dir.return_value = ok
        mock_user_config.return_value = ok
        mock_safety.return_value = ok

        result = run_doctor()

        assert mock_image.call_args_list[0].kwargs == {"provider_id": "claude"}
        assert mock_image.call_args_list[1].kwargs == {"provider_id": "codex"}
        assert mock_auth.call_args_list[0].kwargs == {"provider_id": "claude"}
        assert mock_auth.call_args_list[1].kwargs == {"provider_id": "codex"}
        provider_names = [check.name for check in result.checks if check.category == "provider"]
        assert "Provider Image (Claude Code)" in provider_names
        assert "Provider Image (Codex)" in provider_names
        assert "Provider Auth (Claude Code)" in provider_names
        assert "Provider Auth (Codex)" in provider_names


# ---------------------------------------------------------------------------
# doctor_cmd --provider validation
# ---------------------------------------------------------------------------


class TestDoctorCmdProviderFlag:
    """Verify --provider flag validation in doctor_cmd."""

    def test_unknown_provider_exits_with_code_2(self) -> None:
        """--provider unknown_provider exits with code 2."""
        from click.exceptions import Exit as ClickExit

        from scc_cli.commands.admin import doctor_cmd

        with pytest.raises(ClickExit) as exc_info:
            # Pass all params explicitly — typer defaults are OptionInfo objects
            doctor_cmd(
                workspace=None,
                quick=False,
                json_output=False,
                pretty=False,
                provider="unknown_provider",
            )
        assert exc_info.value.exit_code == 2

    @patch("scc_cli.commands.admin.doctor")
    def test_valid_provider_passes_to_run_doctor(self, mock_doctor: MagicMock) -> None:
        """--provider codex passes provider_id='codex' to run_doctor."""
        from scc_cli.commands.admin import doctor_cmd

        result = DoctorResult()
        result.git_ok = True
        result.docker_ok = True
        result.sandbox_ok = True
        result.checks = [CheckResult(name="Git", passed=True, message="ok")]
        mock_doctor.run_doctor.return_value = result
        mock_doctor.render_doctor_results = MagicMock()

        # Pass all params explicitly — typer defaults are OptionInfo objects
        doctor_cmd(
            workspace=None,
            quick=False,
            json_output=False,
            pretty=False,
            provider="codex",
        )

        mock_doctor.run_doctor.assert_called_once()
        call_kwargs = mock_doctor.run_doctor.call_args
        assert call_kwargs[1].get("provider_id") == "codex" or (
            len(call_kwargs[0]) >= 2 and call_kwargs[0][1] == "codex"
        )


# ---------------------------------------------------------------------------
# build_doctor_json_data includes category
# ---------------------------------------------------------------------------


class TestJsonDataCategory:
    """Verify build_doctor_json_data includes category in each check dict."""

    def test_category_present_in_json(self) -> None:
        result = DoctorResult()
        result.checks = [
            CheckResult(name="Git", passed=True, message="ok", category="backend"),
            CheckResult(name="Provider Image", passed=True, message="ok", category="provider"),
        ]
        data = build_doctor_json_data(result)
        for check_dict in data["checks"]:
            assert "category" in check_dict

    def test_category_values_match(self) -> None:
        result = DoctorResult()
        result.checks = [
            CheckResult(name="Git", passed=True, message="ok", category="backend"),
            CheckResult(name="Config Directory", passed=True, message="ok", category="config"),
        ]
        data = build_doctor_json_data(result)
        assert data["checks"][0]["category"] == "backend"
        assert data["checks"][1]["category"] == "config"


# ---------------------------------------------------------------------------
# Render grouping
# ---------------------------------------------------------------------------


class TestRenderGrouping:
    """Verify render_doctor_results groups checks by category."""

    def test_sort_checks_by_category_order(self) -> None:
        """Checks are sorted: backend → provider → config → worktree → general."""
        checks = [
            CheckResult(name="WSL2", passed=True, message="ok", category="general"),
            CheckResult(name="Provider Image", passed=True, message="ok", category="provider"),
            CheckResult(name="Git", passed=True, message="ok", category="backend"),
            CheckResult(name="Config Directory", passed=True, message="ok", category="config"),
            CheckResult(name="Worktree Health", passed=True, message="ok", category="worktree"),
        ]
        sorted_checks = _sort_checks_by_category(checks)
        categories = [c.category for c in sorted_checks]
        assert categories == ["backend", "provider", "config", "worktree", "general"]

    def test_render_does_not_crash(self) -> None:
        """render_doctor_results runs without error on a valid result."""
        result = DoctorResult()
        result.git_ok = True
        result.docker_ok = True
        result.sandbox_ok = True
        result.checks = [
            CheckResult(name="Git", passed=True, message="ok", category="backend"),
            CheckResult(name="Docker", passed=True, message="ok", category="backend"),
            CheckResult(name="Provider Image", passed=True, message="ok", category="provider"),
            CheckResult(name="Config Directory", passed=True, message="ok", category="config"),
        ]
        console = Console(file=MagicMock(), width=120, force_terminal=True)
        # Should not raise
        render_doctor_results(console, result)

    def test_render_with_failures(self) -> None:
        """render_doctor_results renders failures without crashing."""
        result = DoctorResult()
        result.git_ok = False
        result.docker_ok = False
        result.sandbox_ok = False
        result.checks = [
            CheckResult(name="Git", passed=False, message="not found", category="backend", severity=SeverityLevel.ERROR),
            CheckResult(
                name="Provider Image",
                passed=False,
                message="missing",
                category="provider",
                severity=SeverityLevel.WARNING,
                fix_hint="Build the image",
            ),
        ]
        console = Console(file=MagicMock(), width=120, force_terminal=True)
        # Should not raise
        render_doctor_results(console, result)

    def test_render_success_summary_lists_both_providers_when_unscoped(self) -> None:
        result = DoctorResult()
        result.git_ok = True
        result.docker_ok = True
        result.sandbox_ok = True
        result.checks = [
            CheckResult(name="Git", passed=True, message="ok", category="backend"),
            CheckResult(name="Docker", passed=True, message="ok", category="backend"),
        ]
        console = Console(record=True, width=120, force_terminal=True)

        render_doctor_results(console, result)

        assert "Ready to run Claude Code and Codex." in console.export_text()
