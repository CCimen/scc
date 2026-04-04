"""Tests for network tool detection rules."""

from __future__ import annotations

from scc_cli.core.enums import CommandFamily
from scc_cli.core.network_tool_rules import NETWORK_TOOLS, analyze_network_tool


class TestAnalyzeNetworkTool:
    """Tests for analyze_network_tool function."""

    # ─── Positive: each network tool is blocked ──────────────────────────

    def test_curl_blocked(self) -> None:
        result = analyze_network_tool(["curl", "https://example.com"])
        assert result is not None
        assert result.allowed is False
        assert result.matched_rule == "network.curl"
        assert result.command_family == CommandFamily.NETWORK_TOOL
        assert "curl" in result.reason

    def test_wget_blocked(self) -> None:
        result = analyze_network_tool(["wget", "https://example.com"])
        assert result is not None
        assert result.allowed is False
        assert result.matched_rule == "network.wget"

    def test_ssh_blocked(self) -> None:
        result = analyze_network_tool(["ssh", "user@host"])
        assert result is not None
        assert result.allowed is False
        assert result.matched_rule == "network.ssh"

    def test_scp_blocked(self) -> None:
        result = analyze_network_tool(["scp", "file", "user@host:path"])
        assert result is not None
        assert result.allowed is False
        assert result.matched_rule == "network.scp"

    def test_sftp_blocked(self) -> None:
        result = analyze_network_tool(["sftp", "user@host"])
        assert result is not None
        assert result.allowed is False
        assert result.matched_rule == "network.sftp"

    def test_rsync_blocked(self) -> None:
        result = analyze_network_tool(["rsync", "-avz", "src/", "user@host:dest/"])
        assert result is not None
        assert result.allowed is False
        assert result.matched_rule == "network.rsync"

    # ─── All 6 tools are in the frozenset ────────────────────────────────

    def test_network_tools_count(self) -> None:
        assert len(NETWORK_TOOLS) == 6
        assert NETWORK_TOOLS == frozenset({"curl", "wget", "ssh", "scp", "sftp", "rsync"})

    # ─── Path-qualified binaries detected ────────────────────────────────

    def test_path_qualified_curl(self) -> None:
        result = analyze_network_tool(["/usr/bin/curl", "-s", "https://example.com"])
        assert result is not None
        assert result.allowed is False
        assert result.matched_rule == "network.curl"

    def test_path_qualified_ssh(self) -> None:
        result = analyze_network_tool(["/usr/bin/ssh", "user@host"])
        assert result is not None
        assert result.matched_rule == "network.ssh"

    def test_path_qualified_wget(self) -> None:
        result = analyze_network_tool(["/usr/local/bin/wget", "https://example.com"])
        assert result is not None
        assert result.matched_rule == "network.wget"

    # ─── Negative: non-network commands return None ──────────────────────

    def test_git_allowed(self) -> None:
        assert analyze_network_tool(["git", "push", "origin"]) is None

    def test_ls_allowed(self) -> None:
        assert analyze_network_tool(["ls", "-la"]) is None

    def test_cat_allowed(self) -> None:
        assert analyze_network_tool(["cat", "file.txt"]) is None

    def test_python_allowed(self) -> None:
        assert analyze_network_tool(["python", "-m", "http.server"]) is None

    def test_echo_allowed(self) -> None:
        assert analyze_network_tool(["echo", "curl"]) is None

    # ─── Edge cases and malformed inputs ─────────────────────────────────

    def test_empty_tokens(self) -> None:
        assert analyze_network_tool([]) is None

    def test_single_empty_string(self) -> None:
        assert analyze_network_tool([""]) is None

    def test_tokens_with_only_flags(self) -> None:
        """Tokens that are just flags (no real command)."""
        assert analyze_network_tool(["--verbose", "-x"]) is None

    def test_network_tool_name_as_substring_not_matched(self) -> None:
        """Names that contain a network tool as substring must NOT match."""
        assert analyze_network_tool(["curling"]) is None
        assert analyze_network_tool(["wgetrc"]) is None
        assert analyze_network_tool(["sshmenu"]) is None

    def test_network_tool_as_argument_not_first(self) -> None:
        """Network tool name appearing as an argument (not first token) is fine."""
        assert analyze_network_tool(["echo", "curl"]) is None
        assert analyze_network_tool(["grep", "ssh"]) is None

    def test_bare_tool_no_args(self) -> None:
        """Bare network tool with no arguments still blocked."""
        result = analyze_network_tool(["curl"])
        assert result is not None
        assert result.allowed is False

    # ─── Verdict field correctness ───────────────────────────────────────

    def test_verdict_fields_complete(self) -> None:
        """Verify all SafetyVerdict fields are populated correctly."""
        result = analyze_network_tool(["rsync", "-avz", "src/", "dest/"])
        assert result is not None
        assert result.allowed is False
        assert result.reason.startswith("BLOCKED:")
        assert result.matched_rule == "network.rsync"
        assert result.command_family == CommandFamily.NETWORK_TOOL
