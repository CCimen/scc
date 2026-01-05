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


class TestGitModuleBoundary:
    """git.py facade must have no Rich imports after Phase 4 refactoring.

    Phase 4 acceptance criterion: "git.py has no direct Rich imports"
    """

    def test_git_facade_has_no_rich_imports(self) -> None:
        """git.py must NOT directly import from rich library.

        After Phase 4 refactoring, git.py should be a pure facade that
        re-exports from services/git/ and ui/ without any Rich imports.
        This is a key acceptance criterion from the maintainability plan.
        """
        git_file = SRC / "git.py"
        if not git_file.exists():
            return

        content = git_file.read_text()

        # Check for direct rich imports
        rich_imports = [
            "from rich",
            "import rich",
        ]
        violations = []
        for pattern in rich_imports:
            if pattern in content:
                violations.append(pattern)

        assert not violations, (
            f"git.py should not have Rich imports after Phase 4.\n"
            f"Found: {violations}\n"
            f"Rich imports should be in ui/git_render.py or ui/git_interactive.py"
        )

    def test_git_facade_is_reexports_only(self) -> None:
        """git.py should only contain re-exports, no function definitions.

        After refactoring, git.py should be a thin facade that imports
        and re-exports from other modules. It should not define any
        functions itself.
        """
        git_file = SRC / "git.py"
        if not git_file.exists():
            return

        # Check for function definitions (excluding class methods)
        result = subprocess.run(
            ["grep", "-E", r"^def [a-z_]+\(", str(git_file)],
            capture_output=True,
            text=True,
        )

        # grep returns 0 when matches found, 1 when not
        # We want no matches (returncode 1)
        if result.returncode == 0:
            funcs = result.stdout.strip().split("\n")
            assert False, (
                f"git.py should only contain re-exports, not function definitions.\n"
                f"Found {len(funcs)} function(s):\n{result.stdout}\n"
                f"Move these to services/git/ or ui/git_*.py"
            )


class TestServicesGitBoundary:
    """services/git/ must be pure data layer with no UI dependencies."""

    def test_services_git_has_no_rich_imports(self) -> None:
        """services/git/ modules must NOT import from rich library.

        The services layer should be purely data-focused. Rich imports
        belong in the ui/ layer.
        """
        services_git_path = SRC / "services" / "git"
        if not services_git_path.exists():
            return

        result = subprocess.run(
            ["grep", "-rE", r"(from rich|import rich)", str(services_git_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, (
            f"services/git/ imports rich library:\n{result.stdout}\n"
            f"Move Rich usage to ui/git_render.py or ui/git_interactive.py"
        )

    def test_services_git_has_no_console_params(self) -> None:
        """services/git/ functions should not accept Console parameters.

        Functions that need Console belong in the ui/ layer, not services/.
        """
        services_git_path = SRC / "services" / "git"
        if not services_git_path.exists():
            return

        result = subprocess.run(
            ["grep", "-rE", r"console:\s*Console", str(services_git_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, (
            f"services/git/ has Console parameters:\n{result.stdout}\n"
            f"Functions with Console belong in ui/ layer"
        )

    def test_services_git_does_not_import_ui(self) -> None:
        """services/git/ must not import from ui/."""
        services_git_path = SRC / "services" / "git"
        if not services_git_path.exists():
            return

        result = subprocess.run(
            [
                "grep",
                "-rE",
                r"(from scc_cli\.ui|from \.\.ui|import scc_cli\.ui)",
                str(services_git_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"services/git/ imports ui/:\n{result.stdout}"

    def test_services_git_does_not_import_cli_modules(self) -> None:
        """services/git/ must not import cli_* modules."""
        services_git_path = SRC / "services" / "git"
        if not services_git_path.exists():
            return

        result = subprocess.run(
            [
                "grep",
                "-rE",
                r"(from scc_cli\.cli_|from \.\.cli_|import scc_cli\.cli_)",
                str(services_git_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"services/git/ imports cli_* modules:\n{result.stdout}"


class TestUICanImportServices:
    """Verify UI can properly import from services (positive test)."""

    def test_ui_git_interactive_imports_services(self) -> None:
        """ui/git_interactive.py should import from services/git/."""
        ui_file = SRC / "ui" / "git_interactive.py"
        if not ui_file.exists():
            return

        content = ui_file.read_text()

        # Should import from services/git/
        assert "from ..services.git" in content or "from scc_cli.services.git" in content, (
            "ui/git_interactive.py should import from services/git/"
        )


TESTS = REPO_ROOT / "tests"


class TestCoreWorkspaceBoundary:
    """core/workspace.py must be a pure domain module with no external dependencies."""

    def test_core_workspace_no_services_imports(self) -> None:
        """core/workspace.py must not import from services/."""
        core_workspace = SRC / "core" / "workspace.py"
        if not core_workspace.exists():
            return

        result = subprocess.run(
            [
                "grep",
                "-E",
                r"(from scc_cli\.services|from \.\.services|import scc_cli\.services)",
                str(core_workspace),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"core/workspace.py imports services/:\n{result.stdout}"

    def test_core_workspace_no_ui_imports(self) -> None:
        """core/workspace.py must not import from ui/."""
        core_workspace = SRC / "core" / "workspace.py"
        if not core_workspace.exists():
            return

        result = subprocess.run(
            [
                "grep",
                "-E",
                r"(from scc_cli\.ui|from \.\.ui|import scc_cli\.ui)",
                str(core_workspace),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"core/workspace.py imports ui/:\n{result.stdout}"

    def test_core_workspace_no_commands_imports(self) -> None:
        """core/workspace.py must not import from commands/."""
        core_workspace = SRC / "core" / "workspace.py"
        if not core_workspace.exists():
            return

        result = subprocess.run(
            [
                "grep",
                "-E",
                r"(from scc_cli\.commands|from \.\.commands|import scc_cli\.commands)",
                str(core_workspace),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"core/workspace.py imports commands/:\n{result.stdout}"


class TestServicesWorkspaceBoundary:
    """services/workspace/ must not depend on ui/ or commands/."""

    def test_services_workspace_no_ui_imports(self) -> None:
        """services/workspace/ must not import from ui/."""
        services_workspace_path = SRC / "services" / "workspace"
        if not services_workspace_path.exists():
            return

        result = subprocess.run(
            [
                "grep",
                "-rE",
                r"(from scc_cli\.ui|from \.\.ui|from \.\.\.ui|import scc_cli\.ui)",
                str(services_workspace_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"services/workspace/ imports ui/:\n{result.stdout}"

    def test_services_workspace_no_commands_imports(self) -> None:
        """services/workspace/ must not import from commands/."""
        services_workspace_path = SRC / "services" / "workspace"
        if not services_workspace_path.exists():
            return

        result = subprocess.run(
            [
                "grep",
                "-rE",
                r"(from scc_cli\.commands|from \.\.commands|from \.\.\.commands|import scc_cli\.commands)",
                str(services_workspace_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"services/workspace/ imports commands/:\n{result.stdout}"

    def test_services_workspace_no_cli_modules_imports(self) -> None:
        """services/workspace/ must not import cli_* modules."""
        services_workspace_path = SRC / "services" / "workspace"
        if not services_workspace_path.exists():
            return

        result = subprocess.run(
            [
                "grep",
                "-rE",
                r"(from scc_cli\.cli_|from \.\.cli_|from \.\.\.cli_|import scc_cli\.cli_)",
                str(services_workspace_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, (
            f"services/workspace/ imports cli_* modules:\n{result.stdout}"
        )


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
