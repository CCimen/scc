"""Tests for ImageRef dataclass, image_ref parser, and SCC image constants."""

from __future__ import annotations

import pytest

from scc_cli.core.image_contracts import (
    SCC_BASE_IMAGE,
    SCC_CLAUDE_IMAGE,
    SCC_CLAUDE_IMAGE_REF,
    ImageRef,
    image_ref,
)

# ─────────────────────────────────────────────────────────────────────────────
# ImageRef.full_ref()
# ─────────────────────────────────────────────────────────────────────────────


class TestImageRefFullRef:
    """ImageRef.full_ref() produces correct canonical strings."""

    def test_bare_repository(self) -> None:
        ref = ImageRef(repository="myrepo", tag="latest")
        assert ref.full_ref() == "myrepo:latest"

    def test_repository_with_custom_tag(self) -> None:
        ref = ImageRef(repository="myrepo", tag="v1.2.3")
        assert ref.full_ref() == "myrepo:v1.2.3"

    def test_registry_and_repository(self) -> None:
        ref = ImageRef(registry="ghcr.io", repository="org/myrepo", tag="latest")
        assert ref.full_ref() == "ghcr.io/org/myrepo:latest"

    def test_with_digest_only(self) -> None:
        ref = ImageRef(
            repository="myrepo",
            tag="",
            digest="sha256:abcdef1234567890",
        )
        assert ref.full_ref() == "myrepo@sha256:abcdef1234567890"

    def test_with_tag_and_digest(self) -> None:
        ref = ImageRef(
            registry="ghcr.io",
            repository="org/myrepo",
            tag="v1",
            digest="sha256:abcdef1234567890",
        )
        assert ref.full_ref() == "ghcr.io/org/myrepo:v1@sha256:abcdef1234567890"

    def test_no_registry_with_digest(self) -> None:
        ref = ImageRef(
            repository="myrepo",
            tag="latest",
            digest="sha256:abc123",
        )
        assert ref.full_ref() == "myrepo:latest@sha256:abc123"

    def test_empty_tag_no_digest(self) -> None:
        ref = ImageRef(repository="myrepo", tag="")
        assert ref.full_ref() == "myrepo"


# ─────────────────────────────────────────────────────────────────────────────
# image_ref() parser
# ─────────────────────────────────────────────────────────────────────────────


class TestImageRefParser:
    """image_ref() parses standard Docker reference formats."""

    def test_bare_repo(self) -> None:
        result = image_ref("ubuntu")
        assert result.registry == ""
        assert result.repository == "ubuntu"
        assert result.tag == "latest"
        assert result.digest is None

    def test_repo_with_tag(self) -> None:
        result = image_ref("ubuntu:22.04")
        assert result.registry == ""
        assert result.repository == "ubuntu"
        assert result.tag == "22.04"
        assert result.digest is None

    def test_registry_repo_tag(self) -> None:
        result = image_ref("ghcr.io/org/myrepo:v1.0")
        assert result.registry == "ghcr.io"
        assert result.repository == "org/myrepo"
        assert result.tag == "v1.0"
        assert result.digest is None

    def test_registry_repo_digest(self) -> None:
        result = image_ref("ghcr.io/org/myrepo@sha256:abcdef")
        assert result.registry == "ghcr.io"
        assert result.repository == "org/myrepo"
        assert result.tag == "latest"
        assert result.digest == "sha256:abcdef"

    def test_registry_repo_tag_and_digest(self) -> None:
        result = image_ref("ghcr.io/org/myrepo:v1@sha256:abcdef")
        assert result.registry == "ghcr.io"
        assert result.repository == "org/myrepo"
        assert result.tag == "v1"
        assert result.digest == "sha256:abcdef"

    def test_library_slash_repo(self) -> None:
        """library/ubuntu should keep the full path as repository."""
        result = image_ref("library/ubuntu:22.04")
        assert result.registry == ""
        assert result.repository == "library/ubuntu"
        assert result.tag == "22.04"

    def test_localhost_registry(self) -> None:
        result = image_ref("localhost/myrepo:dev")
        assert result.registry == "localhost"
        assert result.repository == "myrepo"
        assert result.tag == "dev"

    def test_registry_with_port(self) -> None:
        result = image_ref("localhost:5000/myrepo:dev")
        assert result.registry == "localhost:5000"
        assert result.repository == "myrepo"
        assert result.tag == "dev"

    def test_scc_base_roundtrip(self) -> None:
        """Parsing the full_ref of SCC_BASE_IMAGE roundtrips correctly."""
        parsed = image_ref(SCC_BASE_IMAGE.full_ref())
        assert parsed.repository == SCC_BASE_IMAGE.repository
        assert parsed.tag == SCC_BASE_IMAGE.tag

    def test_scc_claude_roundtrip(self) -> None:
        """Parsing the full_ref of SCC_CLAUDE_IMAGE roundtrips correctly."""
        parsed = image_ref(SCC_CLAUDE_IMAGE.full_ref())
        assert parsed.repository == SCC_CLAUDE_IMAGE.repository
        assert parsed.tag == SCC_CLAUDE_IMAGE.tag


# ─────────────────────────────────────────────────────────────────────────────
# ImageRef frozen behavior
# ─────────────────────────────────────────────────────────────────────────────


class TestImageRefFrozen:
    """ImageRef is immutable."""

    def test_cannot_set_field(self) -> None:
        ref = ImageRef(repository="myrepo")
        with pytest.raises(AttributeError):
            ref.repository = "other"  # type: ignore[misc]

    def test_hashable(self) -> None:
        a = ImageRef(repository="repo", tag="v1")
        b = ImageRef(repository="repo", tag="v1")
        assert hash(a) == hash(b)
        assert a == b


# ─────────────────────────────────────────────────────────────────────────────
# SCC image constants
# ─────────────────────────────────────────────────────────────────────────────


class TestSCCImageConstants:
    """SCC-owned image constants have expected values."""

    def test_scc_base_image(self) -> None:
        assert SCC_BASE_IMAGE.repository == "scc-base"
        assert SCC_BASE_IMAGE.tag == "latest"
        assert SCC_BASE_IMAGE.registry == ""
        assert SCC_BASE_IMAGE.digest is None

    def test_scc_claude_image(self) -> None:
        assert SCC_CLAUDE_IMAGE.repository == "scc-agent-claude"
        assert SCC_CLAUDE_IMAGE.tag == "latest"
        assert SCC_CLAUDE_IMAGE.registry == ""
        assert SCC_CLAUDE_IMAGE.digest is None

    def test_scc_claude_image_ref_string(self) -> None:
        assert SCC_CLAUDE_IMAGE_REF == "scc-agent-claude:latest"

    def test_claude_ref_matches_constant(self) -> None:
        """SCC_CLAUDE_IMAGE_REF equals SCC_CLAUDE_IMAGE.full_ref()."""
        assert SCC_CLAUDE_IMAGE_REF == SCC_CLAUDE_IMAGE.full_ref()
