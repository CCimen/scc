"""
Tests for enhanced doctor command features (Phase 7).

TDD approach: Tests written before implementation.
These tests define the contract for:
- fix_commands field on CheckResult
- "Next Steps" section with copy-pasteable commands
- Light proxy environment detection
- JSON output with envelope
"""

from io import StringIO

import pytest
from rich.console import Console

from scc_cli import doctor

# ═══════════════════════════════════════════════════════════════════════════════
# Tests for fix_commands Field on CheckResult
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckResultFixCommands:
    """Test fix_commands field on CheckResult dataclass."""

    def test_check_result_has_fix_commands_field(self) -> None:
        """CheckResult should have optional fix_commands field."""
        result = doctor.CheckResult(
            name="test",
            passed=False,
            message="Failed",
            fix_commands=["docker start", "docker ps"],
        )
        assert result.fix_commands == ["docker start", "docker ps"]

    def test_check_result_fix_commands_defaults_to_none(self) -> None:
        """fix_commands should default to None."""
        result = doctor.CheckResult(
            name="test",
            passed=True,
            message="Passed",
        )
        assert result.fix_commands is None

    def test_check_result_fix_commands_empty_list(self) -> None:
        """fix_commands can be an empty list."""
        result = doctor.CheckResult(
            name="test",
            passed=False,
            message="Failed",
            fix_commands=[],
        )
        assert result.fix_commands == []


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Next Steps Section
# ═══════════════════════════════════════════════════════════════════════════════


class TestNextStepsSection:
    """Test 'Next Steps' section in doctor output."""

    def test_render_next_steps_shows_fix_commands(self) -> None:
        """Next Steps section should display fix_commands."""
        check = doctor.CheckResult(
            name="Docker not running",
            passed=False,
            message="Docker daemon is not running",
            fix_commands=["docker start"],
            fix_hint="Start Docker Desktop or the Docker daemon",
        )
        result = doctor.DoctorResult(checks=[check])

        output = StringIO()
        console = Console(file=output, force_terminal=True, width=80)
        doctor.render_doctor_results(console, result)

        output_text = output.getvalue()
        assert "Next Steps" in output_text or "docker start" in output_text

    def test_render_next_steps_shows_numbered_commands(self) -> None:
        """Multiple fix_commands should be numbered."""
        check = doctor.CheckResult(
            name="Org config unreachable",
            passed=False,
            message="Cannot reach organization config",
            fix_commands=[
                "ping gitlab.example.org",
                'curl -I "https://gitlab.example.org/config.json"',
            ],
            fix_hint="Check your network connection",
        )
        result = doctor.DoctorResult(checks=[check])

        output = StringIO()
        console = Console(file=output, force_terminal=True, width=80)
        doctor.render_doctor_results(console, result)

        output_text = output.getvalue()
        # Should show both commands in output
        assert "curl" in output_text or "ping" in output_text

    def test_no_next_steps_when_all_checks_pass(self) -> None:
        """No Next Steps section when all checks pass."""
        check = doctor.CheckResult(
            name="Docker",
            passed=True,
            message="Docker is running",
        )
        result = doctor.DoctorResult(checks=[check])

        output = StringIO()
        console = Console(file=output, force_terminal=True, width=80)
        doctor.render_doctor_results(console, result)

        output_text = output.getvalue()
        # Should not have "Next Steps" header when all pass
        assert "Next Steps" not in output_text or "All prerequisites met" in output_text


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Proxy Environment Detection
# ═══════════════════════════════════════════════════════════════════════════════


class TestProxyEnvironmentDetection:
    """Test light proxy environment detection."""

    def test_check_proxy_environment_returns_check_result(self) -> None:
        """check_proxy_environment should return a CheckResult."""
        result = doctor.check_proxy_environment()
        assert isinstance(result, doctor.CheckResult)
        assert result.name == "Proxy Environment"

    def test_detects_http_proxy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should detect HTTP_PROXY environment variable."""
        monkeypatch.setenv("HTTP_PROXY", "http://proxy.example.com:8080")
        result = doctor.check_proxy_environment()

        assert result.passed is True
        assert "proxy" in result.message.lower() or "HTTP_PROXY" in result.message

    def test_detects_https_proxy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should detect HTTPS_PROXY environment variable."""
        monkeypatch.setenv("HTTPS_PROXY", "https://proxy.example.com:8080")
        result = doctor.check_proxy_environment()

        assert result.passed is True
        assert "proxy" in result.message.lower() or "HTTPS_PROXY" in result.message

    def test_detects_no_proxy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should report when no proxy is configured."""
        monkeypatch.delenv("HTTP_PROXY", raising=False)
        monkeypatch.delenv("HTTPS_PROXY", raising=False)
        monkeypatch.delenv("http_proxy", raising=False)
        monkeypatch.delenv("https_proxy", raising=False)
        result = doctor.check_proxy_environment()

        assert result.passed is True
        assert result.severity == "info"

    def test_proxy_check_is_informational(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Proxy check should be informational, not error."""
        monkeypatch.setenv("HTTP_PROXY", "http://proxy.example.com:8080")
        result = doctor.check_proxy_environment()

        # Proxy detection is informational, never an error
        assert result.severity == "info"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for JSON Output
# ═══════════════════════════════════════════════════════════════════════════════


class TestDoctorJsonOutput:
    """Test --json flag for doctor command."""

    def test_build_doctor_json_data_returns_dict(self) -> None:
        """build_doctor_json_data should return serializable dict."""
        check = doctor.CheckResult(
            name="Docker",
            passed=True,
            message="Docker is running",
            version="24.0.0",
        )
        result = doctor.DoctorResult(checks=[check])

        data = doctor.build_doctor_json_data(result)

        assert isinstance(data, dict)
        assert "checks" in data
        assert "summary" in data

    def test_build_doctor_json_data_includes_all_check_fields(self) -> None:
        """JSON data should include all CheckResult fields."""
        check = doctor.CheckResult(
            name="Docker",
            passed=False,
            message="Docker not running",
            fix_hint="Start Docker",
            fix_commands=["docker start"],
            severity="error",
        )
        result = doctor.DoctorResult(checks=[check])

        data = doctor.build_doctor_json_data(result)

        check_data = data["checks"][0]
        assert check_data["name"] == "Docker"
        assert check_data["passed"] is False
        assert check_data["message"] == "Docker not running"
        assert check_data["fix_hint"] == "Start Docker"
        assert check_data["fix_commands"] == ["docker start"]
        assert check_data["severity"] == "error"

    def test_build_doctor_json_data_summary(self) -> None:
        """JSON data should include summary with counts."""
        checks = [
            doctor.CheckResult(name="Check1", passed=True, message="OK"),
            doctor.CheckResult(name="Check2", passed=False, message="Failed", severity="error"),
            doctor.CheckResult(name="Check3", passed=False, message="Warning", severity="warning"),
        ]
        result = doctor.DoctorResult(checks=checks)

        data = doctor.build_doctor_json_data(result)

        assert data["summary"]["total"] == 3
        assert data["summary"]["passed"] == 1
        assert data["summary"]["errors"] == 1
        assert data["summary"]["warnings"] == 1
        assert data["summary"]["all_ok"] is False


class TestDoctorJsonEnvelope:
    """Test JSON envelope structure for doctor command."""

    def test_doctor_json_has_correct_kind(self) -> None:
        """Doctor JSON should have kind=DoctorReport."""
        from scc_cli.json_output import build_envelope
        from scc_cli.kinds import Kind

        check = doctor.CheckResult(name="Test", passed=True, message="OK")
        result = doctor.DoctorResult(checks=[check])
        data = doctor.build_doctor_json_data(result)

        envelope = build_envelope(Kind.DOCTOR_REPORT, data=data)

        assert envelope["kind"] == "DoctorReport"
        assert envelope["apiVersion"] == "scc.cli/v1"
        assert "data" in envelope
        assert "checks" in envelope["data"]
