"""Tests for git.py repo-local hooks functionality.

These tests verify the new architecture requirements:
- Repo-local hooks (NOT global)
- SCC_HOOK_MARKER for identifying SCC-managed hooks
- Never overwrite user's existing hooks
- Check hooks.enabled config before installing
"""

import os
from unittest.mock import patch

from scc_cli import git

# ═══════════════════════════════════════════════════════════════════════════════
# Tests for SCC_HOOK_MARKER
# ═══════════════════════════════════════════════════════════════════════════════


class TestSccHookMarker:
    """Tests for SCC_HOOK_MARKER constant."""

    def test_scc_hook_marker_exists(self):
        """SCC_HOOK_MARKER constant should exist."""
        assert hasattr(git, "SCC_HOOK_MARKER")

    def test_scc_hook_marker_is_string(self):
        """SCC_HOOK_MARKER should be a string."""
        assert isinstance(git.SCC_HOOK_MARKER, str)

    def test_scc_hook_marker_value(self):
        """SCC_HOOK_MARKER should have expected value."""
        assert git.SCC_HOOK_MARKER == "# SCC-MANAGED-HOOK"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for is_protected_branch
# ═══════════════════════════════════════════════════════════════════════════════


class TestIsProtectedBranch:
    """Tests for is_protected_branch() function."""

    def test_main_is_protected(self):
        """main branch should be protected."""
        assert git.is_protected_branch("main") is True

    def test_master_is_protected(self):
        """master branch should be protected."""
        assert git.is_protected_branch("master") is True

    def test_develop_is_protected(self):
        """develop branch should be protected."""
        assert git.is_protected_branch("develop") is True

    def test_production_is_protected(self):
        """production branch should be protected."""
        assert git.is_protected_branch("production") is True

    def test_staging_is_protected(self):
        """staging branch should be protected."""
        assert git.is_protected_branch("staging") is True

    def test_feature_branch_not_protected(self):
        """Feature branches should not be protected."""
        assert git.is_protected_branch("feature/my-feature") is False

    def test_claude_prefix_not_protected(self):
        """claude/ branches should not be protected."""
        assert git.is_protected_branch("claude/feature-x") is False

    def test_random_branch_not_protected(self):
        """Random branch names should not be protected."""
        assert git.is_protected_branch("my-branch") is False


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for is_scc_hook
# ═══════════════════════════════════════════════════════════════════════════════


class TestIsSccHook:
    """Tests for is_scc_hook() function."""

    def test_non_existent_hook_returns_false(self, tmp_path):
        """Non-existent hook should return False."""
        hook_path = tmp_path / "pre-push"
        assert git.is_scc_hook(hook_path) is False

    def test_hook_with_scc_marker_returns_true(self, tmp_path):
        """Hook containing SCC marker should return True."""
        hook_path = tmp_path / "pre-push"
        hook_path.write_text(f"""#!/bin/bash
{git.SCC_HOOK_MARKER}
# Some hook content
echo "test"
""")
        assert git.is_scc_hook(hook_path) is True

    def test_hook_without_scc_marker_returns_false(self, tmp_path):
        """Hook without SCC marker should return False (user's hook)."""
        hook_path = tmp_path / "pre-push"
        hook_path.write_text("""#!/bin/bash
# User's custom hook
echo "my custom hook"
""")
        assert git.is_scc_hook(hook_path) is False

    def test_empty_hook_returns_false(self, tmp_path):
        """Empty hook file should return False."""
        hook_path = tmp_path / "pre-push"
        hook_path.write_text("")
        assert git.is_scc_hook(hook_path) is False


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for install_pre_push_hook
# ═══════════════════════════════════════════════════════════════════════════════


class TestInstallPrePushHook:
    """Tests for install_pre_push_hook() function."""

    def test_returns_false_when_hooks_disabled(self, tmp_path):
        """Should return False when hooks.enabled is False in config."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        (repo / ".git" / "hooks").mkdir()

        with patch("scc_cli.config.load_user_config", return_value={"hooks": {"enabled": False}}):
            success, message = git.install_pre_push_hook(repo)

        assert success is False
        assert "not enabled" in message.lower()

    def test_returns_false_when_not_git_repo(self, tmp_path):
        """Should return False when path is not a git repository."""
        not_repo = tmp_path / "not-a-repo"
        not_repo.mkdir()
        # No .git directory

        with patch("scc_cli.config.load_user_config", return_value={"hooks": {"enabled": True}}):
            success, message = git.install_pre_push_hook(not_repo)

        assert success is False
        assert "not a git repository" in message.lower()

    def test_creates_hook_when_none_exists(self, tmp_path):
        """Should create hook when none exists and hooks enabled."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        (repo / ".git" / "hooks").mkdir()

        with patch("scc_cli.config.load_user_config", return_value={"hooks": {"enabled": True}}):
            success, message = git.install_pre_push_hook(repo)

        assert success is True
        assert "installed" in message.lower()

        # Verify hook was created
        hook_path = repo / ".git" / "hooks" / "pre-push"
        assert hook_path.exists()
        assert git.SCC_HOOK_MARKER in hook_path.read_text()

    def test_updates_existing_scc_hook(self, tmp_path):
        """Should update existing SCC hook."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        (repo / ".git" / "hooks").mkdir()

        # Create existing SCC hook
        hook_path = repo / ".git" / "hooks" / "pre-push"
        hook_path.write_text(f"#!/bin/bash\n{git.SCC_HOOK_MARKER}\nold content")

        with patch("scc_cli.config.load_user_config", return_value={"hooks": {"enabled": True}}):
            success, message = git.install_pre_push_hook(repo)

        assert success is True
        assert "updated" in message.lower()

    def test_does_not_overwrite_user_hook(self, tmp_path):
        """Should NOT overwrite user's existing hook (no SCC marker)."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        (repo / ".git" / "hooks").mkdir()

        # Create user's hook without SCC marker
        hook_path = repo / ".git" / "hooks" / "pre-push"
        original_content = "#!/bin/bash\n# User's hook\necho test"
        hook_path.write_text(original_content)

        with patch("scc_cli.config.load_user_config", return_value={"hooks": {"enabled": True}}):
            success, message = git.install_pre_push_hook(repo)

        assert success is False
        assert "will not overwrite" in message.lower()

        # Verify hook was NOT modified
        assert hook_path.read_text() == original_content

    def test_hook_is_executable(self, tmp_path):
        """Created hook should be executable."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        (repo / ".git" / "hooks").mkdir()

        with patch("scc_cli.config.load_user_config", return_value={"hooks": {"enabled": True}}):
            git.install_pre_push_hook(repo)

        hook_path = repo / ".git" / "hooks" / "pre-push"
        # Check executable bit
        assert os.access(hook_path, os.X_OK)

    def test_hook_blocks_protected_branches(self, tmp_path):
        """Created hook should contain logic to block protected branches."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        (repo / ".git" / "hooks").mkdir()

        with patch("scc_cli.config.load_user_config", return_value={"hooks": {"enabled": True}}):
            git.install_pre_push_hook(repo)

        hook_path = repo / ".git" / "hooks" / "pre-push"
        content = hook_path.read_text()

        # Verify hook checks protected branches
        assert "main" in content
        assert "master" in content
        assert "develop" in content
        assert "exit 1" in content


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for _write_scc_hook (internal function)
# ═══════════════════════════════════════════════════════════════════════════════


class TestWriteSccHook:
    """Tests for _write_scc_hook() internal function."""

    def test_writes_hook_with_marker(self, tmp_path):
        """_write_scc_hook should include SCC marker."""
        hook_path = tmp_path / "pre-push"

        git._write_scc_hook(hook_path)

        content = hook_path.read_text()
        assert git.SCC_HOOK_MARKER in content

    def test_writes_executable_hook(self, tmp_path):
        """_write_scc_hook should make hook executable."""
        hook_path = tmp_path / "pre-push"

        git._write_scc_hook(hook_path)

        assert os.access(hook_path, os.X_OK)

    def test_writes_bash_shebang(self, tmp_path):
        """_write_scc_hook should include bash shebang."""
        hook_path = tmp_path / "pre-push"

        git._write_scc_hook(hook_path)

        content = hook_path.read_text()
        assert content.startswith("#!/bin/bash")
