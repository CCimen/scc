"""Structural tests for SCC container images (Dockerfiles).

These tests verify Dockerfile content without requiring Docker.
They parse the Dockerfile text to check expected structural properties:
- scc-base creates both provider config dirs with correct permissions
- scc-agent-codex pins the Codex CLI version via ARG
- Agent user is non-root (uid 1000)
- Build ordering and determinism properties
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

IMAGES_DIR = Path(__file__).resolve().parent.parent / "images"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _read_dockerfile(image_name: str) -> str:
    """Read a Dockerfile from the images/ directory."""
    path = IMAGES_DIR / image_name / "Dockerfile"
    assert path.exists(), f"Dockerfile not found: {path}"
    return path.read_text()


def _normalize_continuations(text: str) -> str:
    """Collapse backslash-newline continuations into single logical lines."""
    return re.sub(r"\\\n\s*", " ", text)


# ─────────────────────────────────────────────────────────────────────────────
# scc-base
# ─────────────────────────────────────────────────────────────────────────────


class TestSccBaseDockerfile:
    """scc-base Dockerfile structural properties."""

    @pytest.fixture()
    def dockerfile(self) -> str:
        return _read_dockerfile("scc-base")

    @pytest.fixture()
    def normalized(self, dockerfile: str) -> str:
        return _normalize_continuations(dockerfile)

    def test_creates_claude_config_dir(self, normalized: str) -> None:
        """scc-base creates /home/agent/.claude directory."""
        assert "/home/agent/.claude" in normalized

    def test_creates_codex_config_dir(self, normalized: str) -> None:
        """scc-base creates /home/agent/.codex directory."""
        assert "/home/agent/.codex" in normalized

    def test_claude_dir_permissions_0700(self, normalized: str) -> None:
        """scc-base sets .claude dir to 0700."""
        chmod_lines = [
            line.strip()
            for line in normalized.splitlines()
            if "chmod" in line and ".claude" in line
        ]
        assert any("0700" in line for line in chmod_lines), (
            f"Expected chmod 0700 on .claude dir, found: {chmod_lines}"
        )

    def test_codex_dir_permissions_0700(self, normalized: str) -> None:
        """scc-base sets .codex dir to 0700."""
        chmod_lines = [
            line.strip()
            for line in normalized.splitlines()
            if "chmod" in line and ".codex" in line
        ]
        assert any("0700" in line for line in chmod_lines), (
            f"Expected chmod 0700 on .codex dir, found: {chmod_lines}"
        )

    def test_agent_user_uid_1000(self, dockerfile: str) -> None:
        """scc-base creates agent user with uid 1000."""
        assert re.search(r"useradd.*-u\s*1000.*agent", dockerfile)

    def test_chown_agent_claude(self, normalized: str) -> None:
        """scc-base chowns .claude to agent:agent."""
        chown_lines = [
            line.strip()
            for line in normalized.splitlines()
            if "chown" in line and ".claude" in line
        ]
        assert any("agent:agent" in line for line in chown_lines), (
            f"Expected chown agent:agent on .claude, found: {chown_lines}"
        )

    def test_chown_agent_codex(self, normalized: str) -> None:
        """scc-base chowns .codex to agent:agent."""
        chown_lines = [
            line.strip()
            for line in normalized.splitlines()
            if "chown" in line and ".codex" in line
        ]
        assert any("agent:agent" in line for line in chown_lines), (
            f"Expected chown agent:agent on .codex, found: {chown_lines}"
        )

    def test_final_user_is_agent(self, dockerfile: str) -> None:
        """scc-base ends with USER agent (non-root)."""
        user_lines = [
            line.strip()
            for line in dockerfile.splitlines()
            if line.strip().startswith("USER ")
        ]
        assert user_lines, "No USER directive found"
        assert user_lines[-1] == "USER agent"

    def test_dirs_created_before_user_switch(self, dockerfile: str) -> None:
        """Provider config dirs are created before switching to agent user."""
        lines = dockerfile.splitlines()
        mkdir_idx = None
        final_user_idx = None
        for i, line in enumerate(lines):
            if "mkdir" in line and (".claude" in line or ".codex" in line):
                mkdir_idx = i
            if line.strip() == "USER agent":
                final_user_idx = i
        assert mkdir_idx is not None, "mkdir for config dirs not found"
        assert final_user_idx is not None, "USER agent not found"
        assert mkdir_idx < final_user_idx, (
            "Config dirs must be created before switching to agent user"
        )

    def test_safety_eval_installed(self, dockerfile: str) -> None:
        """scc-base installs the safety evaluator."""
        assert "scc_safety_eval" in dockerfile

    def test_wrappers_in_path(self, dockerfile: str) -> None:
        """scc-base puts wrapper scripts in PATH."""
        assert "/usr/local/lib/scc/bin" in dockerfile


# ─────────────────────────────────────────────────────────────────────────────
# scc-agent-codex
# ─────────────────────────────────────────────────────────────────────────────


class TestSccAgentCodexDockerfile:
    """scc-agent-codex Dockerfile structural properties."""

    @pytest.fixture()
    def dockerfile(self) -> str:
        return _read_dockerfile("scc-agent-codex")

    @pytest.fixture()
    def normalized(self, dockerfile: str) -> str:
        return _normalize_continuations(dockerfile)

    def test_based_on_scc_base(self, dockerfile: str) -> None:
        """scc-agent-codex inherits from scc-base."""
        assert re.search(r"FROM\s+scc-base", dockerfile)

    def test_codex_version_arg_declared(self, dockerfile: str) -> None:
        """scc-agent-codex declares an ARG for Codex version pinning."""
        assert re.search(r"ARG\s+CODEX_VERSION", dockerfile)

    def test_codex_version_has_default(self, dockerfile: str) -> None:
        """CODEX_VERSION ARG has a default value."""
        assert re.search(r"ARG\s+CODEX_VERSION\s*=", dockerfile)

    def test_npm_install_references_version_arg(self, normalized: str) -> None:
        """npm install uses the CODEX_VERSION ARG."""
        assert "CODEX_VERSION" in normalized
        assert "@openai/codex" in normalized

    def test_installs_nodejs(self, dockerfile: str) -> None:
        """scc-agent-codex installs Node.js."""
        assert "nodejs" in dockerfile

    def test_installs_bubblewrap(self, dockerfile: str) -> None:
        """scc-agent-codex installs system bubblewrap for Codex sandboxing."""
        assert "bubblewrap" in dockerfile

    def test_installs_socat(self, dockerfile: str) -> None:
        """scc-agent-codex installs socat for browser-auth callback relaying."""
        assert "socat" in dockerfile

    def test_final_user_is_agent(self, dockerfile: str) -> None:
        """scc-agent-codex ends with USER agent (non-root)."""
        user_lines = [
            line.strip()
            for line in dockerfile.splitlines()
            if line.strip().startswith("USER ")
        ]
        assert user_lines, "No USER directive found"
        assert user_lines[-1] == "USER agent"

    def test_entrypoint_is_bash(self, dockerfile: str) -> None:
        """scc-agent-codex uses bash entrypoint (OCI adapter execs explicitly)."""
        assert re.search(r'ENTRYPOINT\s+\["/bin/bash"\]', dockerfile)


# ─────────────────────────────────────────────────────────────────────────────
# scc-agent-claude
# ─────────────────────────────────────────────────────────────────────────────


class TestSccAgentClaudeDockerfile:
    """scc-agent-claude Dockerfile structural properties (baseline checks)."""

    @pytest.fixture()
    def dockerfile(self) -> str:
        return _read_dockerfile("scc-agent-claude")

    def test_based_on_scc_base(self, dockerfile: str) -> None:
        """scc-agent-claude inherits from scc-base."""
        assert re.search(r"FROM\s+scc-base", dockerfile)

    def test_node_major_arg_declared(self, dockerfile: str) -> None:
        """scc-agent-claude declares an ARG for Node LTS selection."""
        assert re.search(r"ARG\s+NODE_MAJOR", dockerfile)

    def test_installs_nodejs(self, dockerfile: str) -> None:
        """scc-agent-claude installs Node.js."""
        assert "nodejs" in dockerfile

    def test_nodesource_bootstrap_uses_clean_system_path(self, dockerfile: str) -> None:
        """scc-agent-claude avoids SCC wrapper PATH interception during bootstrap."""
        assert 'export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"' in dockerfile
        assert '/usr/bin/curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x"' in dockerfile

    def test_final_user_is_agent(self, dockerfile: str) -> None:
        """scc-agent-claude ends with USER agent (non-root)."""
        user_lines = [
            line.strip()
            for line in dockerfile.splitlines()
            if line.strip().startswith("USER ")
        ]
        assert user_lines[-1] == "USER agent"

    def test_entrypoint_is_bash(self, dockerfile: str) -> None:
        """scc-agent-claude uses bash entrypoint."""
        assert re.search(r'ENTRYPOINT\s+\["/bin/bash"\]', dockerfile)


# ─────────────────────────────────────────────────────────────────────────────
# scc-egress-proxy
# ─────────────────────────────────────────────────────────────────────────────


class TestSccEgressProxyDockerfile:
    """scc-egress-proxy Dockerfile structural properties (baseline checks)."""

    @pytest.fixture()
    def dockerfile(self) -> str:
        return _read_dockerfile("scc-egress-proxy")

    def test_based_on_alpine(self, dockerfile: str) -> None:
        """scc-egress-proxy uses Alpine base."""
        assert re.search(r"FROM\s+alpine", dockerfile)

    def test_installs_squid(self, dockerfile: str) -> None:
        """scc-egress-proxy installs squid."""
        assert "squid" in dockerfile

    def test_exposes_3128(self, dockerfile: str) -> None:
        """scc-egress-proxy exposes port 3128."""
        assert "3128" in dockerfile

    def test_has_healthcheck(self, dockerfile: str) -> None:
        """scc-egress-proxy has a HEALTHCHECK."""
        assert "HEALTHCHECK" in dockerfile
