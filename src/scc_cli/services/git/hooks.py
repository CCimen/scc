"""Git hooks management - installation and detection.

Pure functions with no UI dependencies.
"""

from pathlib import Path

SCC_HOOK_MARKER = "# SCC-MANAGED-HOOK"  # Identifies hooks we can safely update


def is_scc_hook(hook_path: Path) -> bool:
    """Check if hook file is managed by SCC (has SCC marker).

    Returns:
        True if hook exists and contains SCC_HOOK_MARKER, False otherwise.
    """
    if not hook_path.exists():
        return False
    try:
        content = hook_path.read_text()
        return SCC_HOOK_MARKER in content
    except (OSError, PermissionError):
        return False


def install_pre_push_hook(repo_path: Path) -> tuple[bool, str]:
    """Install repo-local pre-push hook with strict rules.

    Installation conditions:
    1. User said yes in `scc setup` (hooks.enabled=true in config)
    2. Repo is recognized (has .git directory)

    Never:
    - Modify global git config
    - Overwrite existing non-SCC hooks

    Args:
        repo_path: Path to the git repository root

    Returns:
        Tuple of (success, message) describing the outcome
    """
    from ...config import load_user_config

    # Condition 1: Check if hooks are enabled in user config
    config = load_user_config()
    if not config.get("hooks", {}).get("enabled", False):
        return (False, "Hooks not enabled in config")

    # Condition 2: Check if repo is recognized (has .git directory)
    git_dir = repo_path / ".git"
    if not git_dir.exists():
        return (False, "Not a git repository")

    # Determine hooks directory (repo-local, NOT global)
    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_path = hooks_dir / "pre-push"

    # Check for existing hook
    if hook_path.exists():
        if is_scc_hook(hook_path):
            # Safe to update our own hook
            _write_scc_hook(hook_path)
            return (True, "Updated existing SCC hook")
        else:
            # DON'T overwrite user's hook
            return (
                False,
                f"Will not overwrite existing user hook at {hook_path}. "
                f"To manually add SCC protection, add '{SCC_HOOK_MARKER}' marker to your hook.",
            )

    # No existing hook - safe to create
    _write_scc_hook(hook_path)
    return (True, "Installed new SCC hook")


def _write_scc_hook(hook_path: Path) -> None:
    """Write SCC pre-push hook content.

    The hook blocks pushes to protected branches (main, master, develop, production, staging).
    """
    hook_content = f"""#!/bin/bash
{SCC_HOOK_MARKER}
# SCC pre-push hook - blocks pushes to protected branches
# This hook is managed by SCC. You can safely delete it to remove protection.

branch=$(git rev-parse --abbrev-ref HEAD)
protected_branches="main master develop production staging"

for protected in $protected_branches; do
    if [ "$branch" = "$protected" ]; then
        echo ""
        echo "❌ Direct push to '$branch' blocked by SCC"
        echo ""
        echo "Create a feature branch first:"
        echo "  git checkout -b scc/your-feature"
        echo "  git push -u origin scc/your-feature"
        echo ""
        exit 1
    fi
done

exit 0
"""
    hook_path.write_text(hook_content)
    hook_path.chmod(0o755)
