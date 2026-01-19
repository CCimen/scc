"""Project marker detection for workspace resolution.

This module provides functions to detect whether a directory contains
common project markers that indicate it's a valid workspace root.

Project markers include:
- Version control: .git, .gitignore
- SCC config: .scc.yaml
- Package managers: package.json, pyproject.toml, Cargo.toml, go.mod, etc.
- Build systems: Makefile, CMakeLists.txt, build.gradle, etc.
- IDE/editor configs: .project (Eclipse), *.sln (Visual Studio)

This logic is extracted from ui/wizard.py for reuse across the codebase
without UI dependencies, following the architecture principle that
filesystem logic belongs in services, not UI.
"""

from __future__ import annotations

from pathlib import Path

# Common project markers across languages/frameworks
# Split into direct checks (fast) and glob patterns (slower, checked only if needed)
_PROJECT_MARKERS_DIRECT: tuple[str, ...] = (
    ".git",  # Git repository (directory or file for worktrees)
    ".scc.yaml",  # SCC config
    ".gitignore",  # Often at project root
    "package.json",  # Node.js / JavaScript
    "tsconfig.json",  # TypeScript
    "pyproject.toml",  # Python (modern)
    "setup.py",  # Python (legacy)
    "requirements.txt",  # Python dependencies
    "Pipfile",  # Pipenv
    "Cargo.toml",  # Rust
    "go.mod",  # Go
    "pom.xml",  # Java Maven
    "build.gradle",  # Java/Kotlin Gradle
    "gradlew",  # Gradle wrapper (strong signal)
    "Gemfile",  # Ruby
    "composer.json",  # PHP
    "mix.exs",  # Elixir
    "Makefile",  # Make-based projects
    "CMakeLists.txt",  # CMake C/C++
    ".project",  # Eclipse
    "Dockerfile",  # Docker projects
    "docker-compose.yml",  # Docker Compose
    "compose.yaml",  # Docker Compose (new name)
)

# Glob patterns for project markers (checked only if direct checks fail)
_PROJECT_MARKERS_GLOB: tuple[str, ...] = (
    "*.sln",  # .NET solution
    "*.csproj",  # .NET C# project
)


def has_project_markers(path: Path) -> bool:
    """Check if a directory has common project markers.

    Uses a two-phase approach for performance:
    1. Fast direct existence checks for common markers
    2. Slower glob patterns only if direct checks fail

    This function is used to determine whether a directory is likely
    a valid project root (as opposed to a random directory like $HOME).

    Args:
        path: Directory to check.

    Returns:
        True if directory has any recognizable project markers.
    """
    if not path.is_dir():
        return False

    # Phase 1: Fast direct checks
    for marker in _PROJECT_MARKERS_DIRECT:
        if (path / marker).exists():
            return True

    # Phase 2: Slower glob checks (only if no direct markers found)
    for pattern in _PROJECT_MARKERS_GLOB:
        try:
            if next(path.glob(pattern), None) is not None:
                return True
        except (OSError, StopIteration):
            continue

    return False


def is_valid_workspace(path: Path) -> bool:
    """Check if a directory looks like a valid workspace.

    A valid workspace must have at least one of:
    - .git directory or file (for worktrees)
    - .scc.yaml config file
    - Common project markers (package.json, pyproject.toml, etc.)

    Random directories (like $HOME) are NOT valid workspaces.

    Args:
        path: Directory to check.

    Returns:
        True if directory exists and has workspace markers.
    """
    return has_project_markers(path)
