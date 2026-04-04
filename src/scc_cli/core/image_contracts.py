"""Typed image reference contracts and SCC-owned image constants.

Provides a frozen ImageRef dataclass for provider-neutral OCI image
references, a parse helper, and the constant image definitions that
SCC builds and consumes in plain OCI mode.

Usage:
    from scc_cli.core.image_contracts import (
        ImageRef,
        image_ref,
        SCC_BASE_IMAGE,
        SCC_CLAUDE_IMAGE,
        SCC_CLAUDE_IMAGE_REF,
    )
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ImageRef:
    """Immutable OCI image reference with structured fields.

    Attributes:
        registry: Optional registry hostname (e.g. ``ghcr.io``).
        repository: Image repository name (e.g. ``scc-base``).
        tag: Image tag, defaults to ``latest``.
        digest: Optional content-addressable digest (e.g. ``sha256:abc...``).
    """

    repository: str
    registry: str = ""
    tag: str = "latest"
    digest: str | None = None

    def full_ref(self) -> str:
        """Return the canonical image reference string.

        Builds ``[registry/]repository[:tag][@digest]``, omitting
        empty components.
        """
        parts: list[str] = []
        if self.registry:
            parts.append(f"{self.registry}/{self.repository}")
        else:
            parts.append(self.repository)

        if self.tag:
            parts[0] = f"{parts[0]}:{self.tag}"

        if self.digest:
            parts[0] = f"{parts[0]}@{self.digest}"

        return parts[0]


def image_ref(ref_string: str) -> ImageRef:
    """Parse a Docker/OCI image reference string into an ImageRef.

    Handles common formats:
    - ``repo`` → tag defaults to ``latest``
    - ``repo:tag``
    - ``registry/repo:tag``
    - ``registry/repo@sha256:abc...``
    - ``registry/repo:tag@sha256:abc...``

    Args:
        ref_string: Raw image reference string.

    Returns:
        Parsed ImageRef with structured fields.
    """
    digest: str | None = None
    remainder = ref_string

    # Extract digest first (everything after @)
    if "@" in remainder:
        remainder, digest = remainder.rsplit("@", 1)

    # Extract tag (everything after the last colon that isn't part of a port)
    tag = "latest"
    if ":" in remainder:
        # Find the last colon — that separates repo from tag
        before_colon, after_colon = remainder.rsplit(":", 1)
        # If after_colon looks like a port number inside a registry
        # (e.g. localhost:5000/repo), don't treat it as a tag
        if "/" in after_colon:
            # Colon was part of registry:port/repo, no explicit tag
            tag = "latest"
        else:
            tag = after_colon
            remainder = before_colon

    # Split registry from repository on the first slash
    registry = ""
    repository = remainder
    if "/" in remainder:
        first, rest = remainder.split("/", 1)
        # Heuristic: a registry contains a dot, a colon, or is "localhost"
        if "." in first or ":" in first or first == "localhost":
            registry = first
            repository = rest
        else:
            # Treat the whole thing as the repository (e.g. library/ubuntu)
            repository = remainder

    return ImageRef(
        registry=registry,
        repository=repository,
        tag=tag,
        digest=digest,
    )


# ─────────────────────────────────────────────────────────────────────────────
# SCC-Owned Image Constants
# ─────────────────────────────────────────────────────────────────────────────

SCC_BASE_IMAGE = ImageRef(repository="scc-base", tag="latest")

SCC_CLAUDE_IMAGE = ImageRef(repository="scc-agent-claude", tag="latest")

# Plain string for use in SandboxSpec.image and docker commands
SCC_CLAUDE_IMAGE_REF = "scc-agent-claude:latest"
