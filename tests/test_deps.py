"""Tests for deps.py dependency installation module.

These tests verify the new architecture requirements:
- Opt-in dependency detection (--install-deps flag)
- Best-effort installation (warn but continue on failure)
- Strict mode for CI/automation that needs hard failures
- Support for multiple package managers
"""

from unittest.mock import MagicMock, patch

import pytest

from scc_cli import deps

# ═══════════════════════════════════════════════════════════════════════════════
# Tests for detect_package_manager
# ═══════════════════════════════════════════════════════════════════════════════


class TestDetectPackageManager:
    """Tests for detect_package_manager() function."""

    # ── JavaScript/Node.js Package Managers ──

    def test_detects_npm_from_package_lock(self, tmp_path):
        """Should detect npm from package-lock.json."""
        (tmp_path / "package.json").write_text("{}")
        (tmp_path / "package-lock.json").write_text("{}")

        result = deps.detect_package_manager(tmp_path)

        assert result == "npm"

    def test_detects_pnpm_from_pnpm_lock(self, tmp_path):
        """Should detect pnpm from pnpm-lock.yaml."""
        (tmp_path / "package.json").write_text("{}")
        (tmp_path / "pnpm-lock.yaml").write_text("lockfileVersion: 6.0")

        result = deps.detect_package_manager(tmp_path)

        assert result == "pnpm"

    def test_detects_yarn_from_yarn_lock(self, tmp_path):
        """Should detect yarn from yarn.lock."""
        (tmp_path / "package.json").write_text("{}")
        (tmp_path / "yarn.lock").write_text("")

        result = deps.detect_package_manager(tmp_path)

        assert result == "yarn"

    def test_detects_bun_from_bun_lockb(self, tmp_path):
        """Should detect bun from bun.lockb."""
        (tmp_path / "package.json").write_text("{}")
        (tmp_path / "bun.lockb").write_bytes(b"")

        result = deps.detect_package_manager(tmp_path)

        assert result == "bun"

    def test_detects_npm_from_package_json_alone(self, tmp_path):
        """Should fall back to npm if only package.json exists."""
        (tmp_path / "package.json").write_text("{}")

        result = deps.detect_package_manager(tmp_path)

        assert result == "npm"

    # ── Python Package Managers ──

    def test_detects_poetry_from_poetry_lock(self, tmp_path):
        """Should detect poetry from poetry.lock."""
        (tmp_path / "pyproject.toml").write_text("[tool.poetry]")
        (tmp_path / "poetry.lock").write_text("")

        result = deps.detect_package_manager(tmp_path)

        assert result == "poetry"

    def test_detects_uv_from_uv_lock(self, tmp_path):
        """Should detect uv from uv.lock."""
        (tmp_path / "pyproject.toml").write_text("[project]")
        (tmp_path / "uv.lock").write_text("")

        result = deps.detect_package_manager(tmp_path)

        assert result == "uv"

    def test_detects_pip_from_requirements_txt(self, tmp_path):
        """Should detect pip from requirements.txt."""
        (tmp_path / "requirements.txt").write_text("flask==2.0.0")

        result = deps.detect_package_manager(tmp_path)

        assert result == "pip"

    def test_detects_pip_from_pyproject_toml_without_lock(self, tmp_path):
        """Should fall back to pip for pyproject.toml without lock file."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")

        result = deps.detect_package_manager(tmp_path)

        assert result == "pip"

    # ── Java Package Managers ──

    def test_detects_maven_from_pom_xml(self, tmp_path):
        """Should detect maven from pom.xml."""
        (tmp_path / "pom.xml").write_text("<project></project>")

        result = deps.detect_package_manager(tmp_path)

        assert result == "maven"

    def test_detects_gradle_from_build_gradle(self, tmp_path):
        """Should detect gradle from build.gradle."""
        (tmp_path / "build.gradle").write_text("plugins { id 'java' }")

        result = deps.detect_package_manager(tmp_path)

        assert result == "gradle"

    def test_detects_gradle_from_build_gradle_kts(self, tmp_path):
        """Should detect gradle from build.gradle.kts (Kotlin DSL)."""
        (tmp_path / "build.gradle.kts").write_text('plugins { kotlin("jvm") }')

        result = deps.detect_package_manager(tmp_path)

        assert result == "gradle"

    # ── No Detection Cases ──

    def test_returns_none_for_empty_directory(self, tmp_path):
        """Should return None for empty directory."""
        result = deps.detect_package_manager(tmp_path)

        assert result is None

    def test_returns_none_for_unknown_project(self, tmp_path):
        """Should return None for unrecognized project structure."""
        (tmp_path / "README.md").write_text("# My Project")
        (tmp_path / "main.c").write_text("int main() { return 0; }")

        result = deps.detect_package_manager(tmp_path)

        assert result is None

    # ── Priority Tests ──

    def test_lockfile_priority_over_manifest(self, tmp_path):
        """Lock files should take priority over manifest files."""
        # Has both package.json (npm) and pnpm-lock.yaml (pnpm)
        (tmp_path / "package.json").write_text("{}")
        (tmp_path / "pnpm-lock.yaml").write_text("lockfileVersion: 6.0")

        result = deps.detect_package_manager(tmp_path)

        # pnpm lock file should be detected
        assert result == "pnpm"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for get_install_command
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetInstallCommand:
    """Tests for get_install_command() function."""

    def test_npm_install_command(self):
        """npm should use 'npm install'."""
        cmd = deps.get_install_command("npm")
        assert cmd == ["npm", "install"]

    def test_pnpm_install_command(self):
        """pnpm should use 'pnpm install'."""
        cmd = deps.get_install_command("pnpm")
        assert cmd == ["pnpm", "install"]

    def test_yarn_install_command(self):
        """yarn should use 'yarn install'."""
        cmd = deps.get_install_command("yarn")
        assert cmd == ["yarn", "install"]

    def test_bun_install_command(self):
        """bun should use 'bun install'."""
        cmd = deps.get_install_command("bun")
        assert cmd == ["bun", "install"]

    def test_poetry_install_command(self):
        """poetry should use 'poetry install'."""
        cmd = deps.get_install_command("poetry")
        assert cmd == ["poetry", "install"]

    def test_uv_sync_command(self):
        """uv should use 'uv sync'."""
        cmd = deps.get_install_command("uv")
        assert cmd == ["uv", "sync"]

    def test_pip_install_command(self):
        """pip should use 'pip install -r requirements.txt'."""
        cmd = deps.get_install_command("pip")
        assert cmd == ["pip", "install", "-r", "requirements.txt"]

    def test_maven_install_command(self):
        """maven should use 'mvn install'."""
        cmd = deps.get_install_command("maven")
        assert cmd == ["mvn", "install", "-DskipTests"]

    def test_gradle_build_command(self):
        """gradle should use './gradlew build' or 'gradle build'."""
        cmd = deps.get_install_command("gradle")
        # gradle uses 'gradle build' by default, but could be gradlew
        assert cmd[0] in ["gradle", "./gradlew"]
        assert "build" in cmd or "dependencies" in cmd

    def test_unknown_returns_none(self):
        """Unknown package manager should return None."""
        cmd = deps.get_install_command("unknown")
        assert cmd is None


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for install_dependencies
# ═══════════════════════════════════════════════════════════════════════════════


class TestInstallDependencies:
    """Tests for install_dependencies() function."""

    def test_successful_install_returns_true(self, tmp_path):
        """Successful installation should return True."""
        (tmp_path / "package.json").write_text("{}")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = deps.install_dependencies(tmp_path, "npm")

        assert result is True
        mock_run.assert_called_once()

    def test_failed_install_returns_false_in_default_mode(self, tmp_path):
        """Failed installation should return False in default (non-strict) mode."""
        (tmp_path / "package.json").write_text("{}")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            result = deps.install_dependencies(tmp_path, "npm", strict=False)

        assert result is False

    def test_failed_install_raises_in_strict_mode(self, tmp_path):
        """Failed installation should raise in strict mode."""
        (tmp_path / "package.json").write_text("{}")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr=b"error")
            with pytest.raises(deps.DependencyInstallError):
                deps.install_dependencies(tmp_path, "npm", strict=True)

    def test_runs_command_in_workspace_directory(self, tmp_path):
        """Should run install command in the workspace directory."""
        (tmp_path / "package.json").write_text("{}")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            deps.install_dependencies(tmp_path, "npm")

        # Check that cwd was set to workspace
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["cwd"] == tmp_path

    def test_unknown_package_manager_returns_false(self, tmp_path):
        """Unknown package manager should return False (no command to run)."""
        result = deps.install_dependencies(tmp_path, "unknown", strict=False)
        assert result is False

    def test_unknown_package_manager_raises_in_strict_mode(self, tmp_path):
        """Unknown package manager should raise in strict mode."""
        with pytest.raises(deps.DependencyInstallError, match="Unknown package manager"):
            deps.install_dependencies(tmp_path, "unknown", strict=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for DependencyInstallError
# ═══════════════════════════════════════════════════════════════════════════════


class TestDependencyInstallError:
    """Tests for DependencyInstallError exception."""

    def test_exception_exists(self):
        """DependencyInstallError should be defined."""
        assert hasattr(deps, "DependencyInstallError")

    def test_exception_message(self):
        """DependencyInstallError should include package manager in message."""
        err = deps.DependencyInstallError("npm", "Command failed")
        assert "npm" in str(err)
        assert "Command failed" in str(err)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for auto_install_dependencies (convenience function)
# ═══════════════════════════════════════════════════════════════════════════════


class TestAutoInstallDependencies:
    """Tests for auto_install_dependencies() convenience function."""

    def test_detects_and_installs(self, tmp_path):
        """Should detect package manager and install."""
        (tmp_path / "package.json").write_text("{}")
        (tmp_path / "package-lock.json").write_text("{}")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = deps.auto_install_dependencies(tmp_path)

        assert result is True
        # Should have called npm install
        call_args = mock_run.call_args[0][0]
        assert call_args == ["npm", "install"]

    def test_returns_false_if_no_package_manager(self, tmp_path):
        """Should return False if no package manager detected."""
        # Empty directory - no package manager
        result = deps.auto_install_dependencies(tmp_path)
        assert result is False

    def test_strict_mode_propagates(self, tmp_path):
        """Strict mode should propagate to install_dependencies."""
        (tmp_path / "package.json").write_text("{}")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr=b"error")
            with pytest.raises(deps.DependencyInstallError):
                deps.auto_install_dependencies(tmp_path, strict=True)
