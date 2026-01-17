from __future__ import annotations

from typing import Any

from .types import DoctorResult


def build_doctor_json_data(result: DoctorResult) -> dict[str, Any]:
    """Build JSON-serializable data from DoctorResult."""

    checks_data = []
    for check in result.checks:
        check_dict: dict[str, Any] = {
            "name": check.name,
            "passed": check.passed,
            "message": check.message,
            "severity": check.severity,
        }
        if check.version:
            check_dict["version"] = check.version
        if check.fix_hint:
            check_dict["fix_hint"] = check.fix_hint
        if check.fix_url:
            check_dict["fix_url"] = check.fix_url
        if check.fix_commands:
            check_dict["fix_commands"] = check.fix_commands
        if check.code_frame:
            check_dict["code_frame"] = check.code_frame
        checks_data.append(check_dict)

    total = len(result.checks)
    passed = sum(1 for c in result.checks if c.passed)
    errors = sum(1 for c in result.checks if not c.passed and c.severity == "error")
    warnings = sum(1 for c in result.checks if not c.passed and c.severity == "warning")

    return {
        "checks": checks_data,
        "summary": {
            "total": total,
            "passed": passed,
            "errors": errors,
            "warnings": warnings,
            "all_ok": result.all_ok,
        },
    }
