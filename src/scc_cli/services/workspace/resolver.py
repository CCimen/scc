"""Workspace resolution service.

This module provides the main entry point for resolving workspace context
for the launch command. It implements the Smart Start resolution logic.

Resolution Policy (simple, explicit):
1. If --workspace provided: Use that path (explicit mode)
2. If cwd is in a git repo: Use git root (auto-detect)
3. If .scc.yaml found in parent walk: Use config parent dir (auto-detect)
4. Otherwise: Return None (requires wizard or explicit path)

Path Canonicalization:
All paths in the result are canonicalized via Path.resolve() to ensure:
- Symlinks are expanded
- Relative paths become absolute
- Consistent comparison semantics

Container Workdir (CW) Calculation:
- CW = str(ED) if ED is within MR, else str(WR)
- Uses realpath semantics for "within" check to prevent symlink escape
"""

from __future__ import annotations

from pathlib import Path

from scc_cli.core.workspace import ResolverResult
from scc_cli.services.git.worktree import get_workspace_mount_path
from scc_cli.subprocess_utils import run_command

from .suspicious import is_suspicious_directory


def _is_path_within(child: Path, parent: Path) -> bool:
    """Check if child path is within parent path using resolved paths.

    Both paths are resolved to handle symlinks properly. This prevents
    symlink escape attacks where a symlink outside the mount could
    trick the check.

    Args:
        child: The potential child path.
        parent: The potential parent path.

    Returns:
        True if child is equal to or under parent.
    """
    try:
        child_resolved = child.resolve()
        parent_resolved = parent.resolve()
        # Check if child is equal to parent or is a descendant
        return child_resolved == parent_resolved or parent_resolved in child_resolved.parents
    except OSError:
        # Path resolution failed - be conservative
        return False


def _detect_git_root(cwd: Path) -> Path | None:
    """Detect git repository root from cwd using git rev-parse.

    This handles:
    - Regular git repos
    - Subdirectories within repos
    - Git worktrees

    Args:
        cwd: Current working directory.

    Returns:
        Git repository root path, or None if not in a git repo.
    """
    toplevel = run_command(
        ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
        timeout=5,
    )
    if toplevel:
        return Path(toplevel.strip()).resolve()
    return None


def _detect_scc_config_root(cwd: Path) -> Path | None:
    """Find .scc.yaml by walking up from cwd.

    Args:
        cwd: Current working directory.

    Returns:
        Directory containing .scc.yaml, or None if not found.
    """
    current = cwd.resolve()
    while current != current.parent:
        scc_config = current / ".scc.yaml"
        if scc_config.is_file():
            return current
        current = current.parent
    return None


def _calculate_container_workdir(
    entry_dir: Path,
    mount_root: Path,
    workspace_root: Path,
) -> str:
    """Calculate the container working directory.

    The container workdir follows a simple rule:
    - If entry_dir is within mount_root, use entry_dir as container cwd
    - Otherwise, use workspace_root as container cwd

    This preserves the user's subdirectory context when launching from
    within a project, while falling back to workspace root when the
    entry point is outside the mount scope.

    Args:
        entry_dir: Where the user invoked from (ED).
        mount_root: The host path mounted into the container (MR).
        workspace_root: The workspace root (WR).

    Returns:
        Container working directory as absolute path string.
    """
    if _is_path_within(entry_dir, mount_root):
        return str(entry_dir.resolve())
    return str(workspace_root.resolve())


def resolve_launch_context(
    cwd: Path,
    workspace_arg: str | None,
    *,
    allow_suspicious: bool = False,
) -> ResolverResult | None:
    """Resolve workspace with complete context for launch.

    This is the main entry point for workspace resolution. It implements
    the Smart Start logic to determine workspace root, mount path, and
    container working directory.

    Auto-detect policy (simple, explicit):
    1. git rev-parse --show-toplevel -> use git root
    2. .scc.yaml parent walk -> use config dir
    3. Anything else -> None (requires wizard or explicit path)

    Suspicious handling:
    - Auto-detected + suspicious -> is_suspicious=True (blocks auto-launch)
    - .scc.yaml resolving WR to suspicious (e.g., HOME) -> is_suspicious=True
    - Explicit + suspicious + allow_suspicious=False -> is_suspicious=True
    - Explicit + suspicious + allow_suspicious=True -> proceed (user confirmed)

    Args:
        cwd: Current working directory (where user invoked from).
        workspace_arg: Explicit workspace path from --workspace arg, or None.
        allow_suspicious: If True, allow explicit paths to suspicious locations.
            This is typically set via --force or after user confirmation.

    Returns:
        ResolverResult with all paths canonicalized, or None if:
        - No workspace could be auto-detected AND no explicit path provided
        - Explicit path doesn't exist
    """
    entry_dir = cwd.resolve()
    is_auto_detected = workspace_arg is None

    # Determine workspace root
    if workspace_arg is not None:
        # Explicit --workspace provided
        workspace_path = Path(workspace_arg).expanduser()
        if not workspace_path.is_absolute():
            workspace_path = (cwd / workspace_path).resolve()
        else:
            workspace_path = workspace_path.resolve()

        if not workspace_path.exists():
            # Explicit path doesn't exist - return None
            return None

        workspace_root = workspace_path
        reason = f"Explicit --workspace: {workspace_arg}"
    else:
        # Auto-detection: try git first, then .scc.yaml
        git_root = _detect_git_root(cwd)
        if git_root is not None:
            workspace_root = git_root
            reason = f"Git repository detected at: {git_root}"
        else:
            scc_config_root = _detect_scc_config_root(cwd)
            if scc_config_root is not None:
                workspace_root = scc_config_root
                reason = f".scc.yaml found at: {scc_config_root}"
            else:
                # No auto-detection possible
                return None

    # Check if workspace root is suspicious
    is_suspicious = is_suspicious_directory(workspace_root)

    # For explicit paths with allow_suspicious=True, clear the flag
    # (user has confirmed they want to use this location)
    if not is_auto_detected and allow_suspicious and is_suspicious:
        # User explicitly confirmed - still report as suspicious but allow
        # The caller can check is_auto_eligible() to see if it needs confirmation
        pass

    # Determine mount root (may expand for worktrees)
    mount_root, is_mount_expanded = get_workspace_mount_path(workspace_root)

    # Calculate container working directory
    container_workdir = _calculate_container_workdir(
        entry_dir,
        mount_root,
        workspace_root,
    )

    return ResolverResult(
        workspace_root=workspace_root,
        entry_dir=entry_dir,
        mount_root=mount_root,
        container_workdir=container_workdir,
        is_auto_detected=is_auto_detected,
        is_suspicious=is_suspicious,
        is_mount_expanded=is_mount_expanded,
        reason=reason,
    )
