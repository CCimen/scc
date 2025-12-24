"""Characterization tests for doctor.py refactoring.

These tests freeze the public API and output structure of doctor.py
to ensure the refactoring into a package structure doesn't break
any existing functionality.

Created as part of Phase 0 (Safety Net) for the doctor.py refactoring.
"""

from scc_cli import doctor

# ═══════════════════════════════════════════════════════════════════════════════
# Tests for build_doctor_json_data Output Structure
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildDoctorJsonDataStructure:
    """Freeze the JSON output structure from build_doctor_json_data."""

    def test_returns_dict_with_required_keys(self) -> None:
        """Output dict must have 'checks' and 'summary' keys."""
        result = doctor.DoctorResult(checks=[])
        data = doctor.build_doctor_json_data(result)

        assert isinstance(data, dict)
        assert "checks" in data
        assert "summary" in data

    def test_checks_is_list(self) -> None:
        """'checks' must be a list."""
        result = doctor.DoctorResult(checks=[])
        data = doctor.build_doctor_json_data(result)

        assert isinstance(data["checks"], list)

    def test_summary_has_required_fields(self) -> None:
        """Summary must have total, passed, errors, warnings, all_ok."""
        result = doctor.DoctorResult(checks=[])
        data = doctor.build_doctor_json_data(result)
        summary = data["summary"]

        assert "total" in summary
        assert "passed" in summary
        assert "errors" in summary
        assert "warnings" in summary
        assert "all_ok" in summary

    def test_summary_field_types(self) -> None:
        """Summary fields have correct types."""
        result = doctor.DoctorResult(checks=[])
        data = doctor.build_doctor_json_data(result)
        summary = data["summary"]

        assert isinstance(summary["total"], int)
        assert isinstance(summary["passed"], int)
        assert isinstance(summary["errors"], int)
        assert isinstance(summary["warnings"], int)
        assert isinstance(summary["all_ok"], bool)

    def test_check_entry_has_required_fields(self) -> None:
        """Each check entry must have name, passed, message, severity."""
        check = doctor.CheckResult(
            name="Test Check",
            passed=True,
            message="Test passed",
            severity="info",
        )
        result = doctor.DoctorResult(checks=[check])
        data = doctor.build_doctor_json_data(result)

        assert len(data["checks"]) == 1
        check_data = data["checks"][0]

        assert "name" in check_data
        assert "passed" in check_data
        assert "message" in check_data
        assert "severity" in check_data

    def test_check_entry_required_field_types(self) -> None:
        """Check entry required fields have correct types."""
        check = doctor.CheckResult(
            name="Test Check",
            passed=True,
            message="Test message",
            severity="info",
        )
        result = doctor.DoctorResult(checks=[check])
        data = doctor.build_doctor_json_data(result)

        check_data = data["checks"][0]
        assert isinstance(check_data["name"], str)
        assert isinstance(check_data["passed"], bool)
        assert isinstance(check_data["message"], str)
        assert isinstance(check_data["severity"], str)

    def test_check_entry_optional_fields_included_when_present(self) -> None:
        """Optional fields are included when set on CheckResult."""
        check = doctor.CheckResult(
            name="Test Check",
            passed=False,
            message="Test failed",
            severity="error",
            version="1.2.3",
            fix_hint="Try this fix",
            fix_url="https://example.com/docs",
            fix_commands=["cmd1", "cmd2"],
            code_frame="  1 | error here\n    | ^^^^^",
        )
        result = doctor.DoctorResult(checks=[check])
        data = doctor.build_doctor_json_data(result)

        check_data = data["checks"][0]
        assert check_data.get("version") == "1.2.3"
        assert check_data.get("fix_hint") == "Try this fix"
        assert check_data.get("fix_url") == "https://example.com/docs"
        assert check_data.get("fix_commands") == ["cmd1", "cmd2"]
        assert check_data.get("code_frame") == "  1 | error here\n    | ^^^^^"

    def test_check_entry_optional_fields_excluded_when_none(self) -> None:
        """Optional fields are NOT included when None."""
        check = doctor.CheckResult(
            name="Test Check",
            passed=True,
            message="Passed",
        )
        result = doctor.DoctorResult(checks=[check])
        data = doctor.build_doctor_json_data(result)

        check_data = data["checks"][0]
        # These should NOT be in the dict (not just None-valued)
        assert "version" not in check_data
        assert "fix_hint" not in check_data
        assert "fix_url" not in check_data
        assert "fix_commands" not in check_data
        assert "code_frame" not in check_data

    def test_summary_counts_are_correct(self) -> None:
        """Summary statistics are calculated correctly."""
        checks = [
            doctor.CheckResult(name="Pass1", passed=True, message="OK"),
            doctor.CheckResult(name="Pass2", passed=True, message="OK"),
            doctor.CheckResult(name="Error1", passed=False, message="Fail", severity="error"),
            doctor.CheckResult(name="Warning1", passed=False, message="Warn", severity="warning"),
        ]
        result = doctor.DoctorResult(checks=checks)
        data = doctor.build_doctor_json_data(result)
        summary = data["summary"]

        assert summary["total"] == 4
        assert summary["passed"] == 2
        assert summary["errors"] == 1
        assert summary["warnings"] == 1
        assert summary["all_ok"] is False

    def test_all_ok_true_when_prerequisites_met(self) -> None:
        """all_ok is True when git_ok, docker_ok, sandbox_ok are all True."""
        checks = [
            doctor.CheckResult(name="Pass1", passed=True, message="OK"),
            doctor.CheckResult(name="Pass2", passed=True, message="OK"),
        ]
        result = doctor.DoctorResult(
            git_ok=True,
            docker_ok=True,
            sandbox_ok=True,
            checks=checks,
        )
        data = doctor.build_doctor_json_data(result)

        assert data["summary"]["all_ok"] is True

    def test_multiple_checks_preserve_order(self) -> None:
        """Checks are in the same order as input."""
        checks = [
            doctor.CheckResult(name="First", passed=True, message="1"),
            doctor.CheckResult(name="Second", passed=True, message="2"),
            doctor.CheckResult(name="Third", passed=True, message="3"),
        ]
        result = doctor.DoctorResult(checks=checks)
        data = doctor.build_doctor_json_data(result)

        names = [c["name"] for c in data["checks"]]
        assert names == ["First", "Second", "Third"]


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Public API Exports (Regression Guard)
# ═══════════════════════════════════════════════════════════════════════════════


class TestPublicAPIExports:
    """Ensure all public API items remain accessible after refactoring."""

    def test_checkresult_dataclass_accessible(self) -> None:
        """CheckResult must be importable from doctor module."""
        assert hasattr(doctor, "CheckResult")
        # Verify it's a dataclass with expected fields
        obj = doctor.CheckResult(name="Test", passed=True, message="OK")
        assert obj.name == "Test"
        assert obj.passed is True
        assert obj.message == "OK"

    def test_doctorresult_dataclass_accessible(self) -> None:
        """DoctorResult must be importable from doctor module."""
        assert hasattr(doctor, "DoctorResult")
        obj = doctor.DoctorResult(checks=[])
        assert obj.checks == []

    def test_jsonvalidationresult_dataclass_accessible(self) -> None:
        """JsonValidationResult must be importable from doctor module."""
        assert hasattr(doctor, "JsonValidationResult")
        obj = doctor.JsonValidationResult(valid=True)
        assert obj.valid is True

    def test_run_doctor_function_accessible(self) -> None:
        """run_doctor must be importable from doctor module."""
        assert hasattr(doctor, "run_doctor")
        assert callable(doctor.run_doctor)

    def test_build_doctor_json_data_function_accessible(self) -> None:
        """build_doctor_json_data must be importable from doctor module."""
        assert hasattr(doctor, "build_doctor_json_data")
        assert callable(doctor.build_doctor_json_data)

    def test_render_doctor_results_function_accessible(self) -> None:
        """render_doctor_results must be importable from doctor module."""
        assert hasattr(doctor, "render_doctor_results")
        assert callable(doctor.render_doctor_results)

    def test_render_quick_status_function_accessible(self) -> None:
        """render_quick_status must be importable from doctor module."""
        assert hasattr(doctor, "render_quick_status")
        assert callable(doctor.render_quick_status)

    def test_quick_check_function_accessible(self) -> None:
        """quick_check must be importable from doctor module."""
        assert hasattr(doctor, "quick_check")
        assert callable(doctor.quick_check)

    def test_is_first_run_function_accessible(self) -> None:
        """is_first_run must be importable from doctor module."""
        assert hasattr(doctor, "is_first_run")
        assert callable(doctor.is_first_run)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for DoctorResult Properties (Computed Fields)
# ═══════════════════════════════════════════════════════════════════════════════


class TestDoctorResultProperties:
    """Freeze DoctorResult computed property behavior."""

    def test_all_ok_property_true_when_prerequisites_met(self) -> None:
        """all_ok returns True when git_ok, docker_ok, sandbox_ok are True."""
        result = doctor.DoctorResult(
            git_ok=True,
            docker_ok=True,
            sandbox_ok=True,
            checks=[],
        )
        assert result.all_ok is True

    def test_all_ok_property_false_when_git_missing(self) -> None:
        """all_ok returns False when git_ok is False."""
        result = doctor.DoctorResult(
            git_ok=False,
            docker_ok=True,
            sandbox_ok=True,
        )
        assert result.all_ok is False

    def test_all_ok_property_false_when_docker_missing(self) -> None:
        """all_ok returns False when docker_ok is False."""
        result = doctor.DoctorResult(
            git_ok=True,
            docker_ok=False,
            sandbox_ok=True,
        )
        assert result.all_ok is False

    def test_all_ok_property_false_when_sandbox_missing(self) -> None:
        """all_ok returns False when sandbox_ok is False."""
        result = doctor.DoctorResult(
            git_ok=True,
            docker_ok=True,
            sandbox_ok=False,
        )
        assert result.all_ok is False

    def test_error_count_property_counts_errors(self) -> None:
        """error_count returns count of failed error-severity checks."""
        checks = [
            doctor.CheckResult(name="Error1", passed=False, message="Fail", severity="error"),
            doctor.CheckResult(name="Error2", passed=False, message="Fail", severity="error"),
            doctor.CheckResult(name="Warn", passed=False, message="Warn", severity="warning"),
        ]
        result = doctor.DoctorResult(checks=checks)
        assert result.error_count == 2

    def test_error_count_property_zero_when_no_errors(self) -> None:
        """error_count returns 0 when no error-severity checks fail."""
        checks = [
            doctor.CheckResult(name="Warn", passed=False, message="Warn", severity="warning"),
        ]
        result = doctor.DoctorResult(checks=checks)
        assert result.error_count == 0

    def test_warning_count_property_counts_warnings(self) -> None:
        """warning_count returns count of failed warning-severity checks."""
        checks = [
            doctor.CheckResult(name="Warn1", passed=False, message="Warn", severity="warning"),
            doctor.CheckResult(name="Warn2", passed=False, message="Warn", severity="warning"),
            doctor.CheckResult(name="Error", passed=False, message="Fail", severity="error"),
        ]
        result = doctor.DoctorResult(checks=checks)
        assert result.warning_count == 2

    def test_warning_count_property_zero_when_no_warnings(self) -> None:
        """warning_count returns 0 when no warning-severity checks fail."""
        checks = [
            doctor.CheckResult(name="Error", passed=False, message="Fail", severity="error"),
        ]
        result = doctor.DoctorResult(checks=checks)
        assert result.warning_count == 0
