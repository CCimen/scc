"""Enforce dependency direction rules at package boundaries.

Dependency Direction Rules:
    Commands/UI -> Core/Services -> Utils

    - Domain packages (doctor/, docker/, marketplace/, evaluation/) must NOT
      import CLI surface modules (cli_*.py)
    - Core packages (when created) must NOT import ui/
    - Services packages (when created) must NOT import commands/

This test file uses grep-based boundary tests (not just cycle detection) to catch
bad-direction imports that don't form a cycle.
"""

import subprocess
from pathlib import Path

# Use absolute paths relative to this test file
REPO_ROOT = Path(__file__).parent.parent
SRC = REPO_ROOT / "src" / "scc_cli"


class TestDomainDoesNotImportCLI:
    """Domain/service packages must not depend on CLI surface modules."""

    def test_doctor_does_not_import_cli_modules(self) -> None:
        """doctor/ must not depend on cli_*.py modules."""
        result = subprocess.run(
            [
                "grep",
                "-rE",
                r"(from scc_cli\.cli_|from \.cli_|import scc_cli\.cli_)",
                str(SRC / "doctor"),
            ],
            capture_output=True,
            text=True,
        )
        # grep returns 1 when no matches found (which is what we want)
        assert result.returncode == 1, f"doctor/ imports cli_* modules:\n{result.stdout}"

    def test_docker_does_not_import_cli_modules(self) -> None:
        """docker/ must not depend on cli_*.py modules."""
        result = subprocess.run(
            [
                "grep",
                "-rE",
                r"(from scc_cli\.cli_|from \.cli_|import scc_cli\.cli_)",
                str(SRC / "docker"),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"docker/ imports cli_* modules:\n{result.stdout}"

    def test_marketplace_does_not_import_cli_modules(self) -> None:
        """marketplace/ must not depend on cli_*.py modules."""
        result = subprocess.run(
            [
                "grep",
                "-rE",
                r"(from scc_cli\.cli_|from \.cli_|import scc_cli\.cli_)",
                str(SRC / "marketplace"),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"marketplace/ imports cli_* modules:\n{result.stdout}"

    def test_evaluation_does_not_import_cli_modules(self) -> None:
        """evaluation/ must not depend on cli_*.py modules."""
        result = subprocess.run(
            [
                "grep",
                "-rE",
                r"(from scc_cli\.cli_|from \.cli_|import scc_cli\.cli_)",
                str(SRC / "evaluation"),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"evaluation/ imports cli_* modules:\n{result.stdout}"

    def test_utils_does_not_import_cli_modules(self) -> None:
        """utils/ must not depend on cli_*.py modules."""
        result = subprocess.run(
            [
                "grep",
                "-rE",
                r"(from scc_cli\.cli_|from \.cli_|import scc_cli\.cli_)",
                str(SRC / "utils"),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"utils/ imports cli_* modules:\n{result.stdout}"


class TestFutureLayerBoundaries:
    """Tests for future package structure (core/, services/).

    These tests are skipped until the packages are created in Phase 4-5.
    They establish the expected boundaries for the target architecture.
    """

    def test_core_does_not_import_ui(self) -> None:
        """core/ must not depend on ui/."""
        core_path = SRC / "core"
        if not core_path.exists():
            # Package not yet created - test passes vacuously
            return

        result = subprocess.run(
            [
                "grep",
                "-rE",
                r"(from scc_cli\.ui|import scc_cli\.ui)",
                str(core_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"core/ imports ui/:\n{result.stdout}"

    def test_services_does_not_import_commands(self) -> None:
        """services/ must not depend on commands/."""
        services_path = SRC / "services"
        if not services_path.exists():
            # Package not yet created - test passes vacuously
            return

        result = subprocess.run(
            [
                "grep",
                "-rE",
                r"(from scc_cli\.commands|import scc_cli\.commands)",
                str(services_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"services/ imports commands/:\n{result.stdout}"

    def test_core_does_not_import_commands(self) -> None:
        """core/ must not depend on commands/."""
        core_path = SRC / "core"
        if not core_path.exists():
            return

        result = subprocess.run(
            [
                "grep",
                "-rE",
                r"(from scc_cli\.commands|import scc_cli\.commands)",
                str(core_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"core/ imports commands/:\n{result.stdout}"


TESTS = REPO_ROOT / "tests"


class TestNoTestFileDuplicates:
    """Prevent test file duplication patterns that lead to clutter.

    Rule: No deprecated/legacy test files. If a test is obsolete, remove it
    in the same PR that replaces it.

    Naming patterns that indicate duplication:
    - *_new.py: Suggests an old version exists
    - *_legacy.py: Explicitly deprecated
    - *_characterization.py: Safety nets that should be temporary

    Exception: Files can be explicitly allowlisted with a tracking issue link.
    """

    # Allowlist: files with explicit justification and tracking issue
    ALLOWED_FILES: set[str] = set()  # Add files here with issue links if needed

    def test_no_new_suffix_test_files(self) -> None:
        """Test files should not have _new suffix (implies duplicate exists)."""
        new_files = list(TESTS.glob("test_*_new.py"))
        # Filter out allowlisted files
        unexpected = [f for f in new_files if f.name not in self.ALLOWED_FILES]

        assert not unexpected, (
            f"Found test files with _new suffix (suggests duplication):\n"
            f"{chr(10).join(str(f) for f in unexpected)}\n\n"
            f"If replacing a test file, delete the old one in the same PR.\n"
            f"If this is intentional, add to ALLOWED_FILES with issue link."
        )

    def test_no_legacy_suffix_test_files(self) -> None:
        """Test files should not have _legacy suffix."""
        legacy_files = list(TESTS.glob("test_*_legacy.py"))
        unexpected = [f for f in legacy_files if f.name not in self.ALLOWED_FILES]

        assert not unexpected, (
            f"Found test files with _legacy suffix:\n"
            f"{chr(10).join(str(f) for f in unexpected)}\n\n"
            f"Legacy test files should be deleted, not kept indefinitely."
        )

    def test_no_characterization_suffix_test_files(self) -> None:
        """Characterization tests should be temporary safety nets."""
        char_files = list(TESTS.glob("test_*_characterization.py"))
        unexpected = [f for f in char_files if f.name not in self.ALLOWED_FILES]

        assert not unexpected, (
            f"Found characterization test files:\n"
            f"{chr(10).join(str(f) for f in unexpected)}\n\n"
            f"Characterization tests are temporary refactoring safety nets.\n"
            f"Convert to proper tests and delete when refactoring is complete."
        )
