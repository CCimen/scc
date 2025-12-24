"""
Provide dependency detection and installation for project workspaces.

Offer opt-in dependency installation that:
- Is opt-in (--install-deps flag)
- Never blocks scc start by default
- Supports strict mode for CI/automation that needs hard failures

Supported package managers:
- JavaScript: npm, pnpm, yarn, bun
- Python: poetry, uv, pip
- Java: maven, gradle
"""

import subprocess
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════════
# Exception Classes
# ═══════════════════════════════════════════════════════════════════════════════


class DependencyInstallError(Exception):
    """Raised when dependency installation fails in strict mode."""

    def __init__(self, package_manager: str, message: str):
        self.package_manager = package_manager
        self.message = message
        super().__init__(f"{package_manager}: {message}")


# ═══════════════════════════════════════════════════════════════════════════════
# Package Manager Detection
# ═══════════════════════════════════════════════════════════════════════════════

# Detection order matters - lock files take priority over manifest files
DETECTION_ORDER = [
    # JavaScript lock files (priority)
    ("pnpm-lock.yaml", "pnpm"),
    ("yarn.lock", "yarn"),
    ("bun.lockb", "bun"),
    ("package-lock.json", "npm"),
    # Python lock files (priority)
    ("uv.lock", "uv"),
    ("poetry.lock", "poetry"),
    # Java build files
    ("pom.xml", "maven"),
    ("build.gradle.kts", "gradle"),
    ("build.gradle", "gradle"),
    # Fallback manifest files
    ("package.json", "npm"),  # JS fallback
    ("pyproject.toml", "pip"),  # Python fallback
    ("requirements.txt", "pip"),
]


def detect_package_manager(workspace: Path) -> str | None:
    """Detect the package manager from project files.

    Base detection on the presence of lock files and manifest files.
    Give lock files priority over manifest files.

    Args:
        workspace: Path to the project workspace

    Returns:
        Package manager name or None if not detected.
        Possible values: 'npm', 'pnpm', 'yarn', 'bun', 'poetry', 'uv', 'pip', 'maven', 'gradle'
    """
    for filename, package_manager in DETECTION_ORDER:
        if (workspace / filename).exists():
            return package_manager

    return None


# ═══════════════════════════════════════════════════════════════════════════════
# Install Commands
# ═══════════════════════════════════════════════════════════════════════════════

INSTALL_COMMANDS = {
    # JavaScript
    "npm": ["npm", "install"],
    "pnpm": ["pnpm", "install"],
    "yarn": ["yarn", "install"],
    "bun": ["bun", "install"],
    # Python
    "poetry": ["poetry", "install"],
    "uv": ["uv", "sync"],
    "pip": ["pip", "install", "-r", "requirements.txt"],
    # Java
    "maven": ["mvn", "install", "-DskipTests"],
    "gradle": ["gradle", "dependencies"],
}


def get_install_command(package_manager: str) -> list[str] | None:
    """Return the install command for a package manager.

    Args:
        package_manager: Name of the package manager

    Returns:
        List of command arguments or None if unknown
    """
    return INSTALL_COMMANDS.get(package_manager)


# ═══════════════════════════════════════════════════════════════════════════════
# Dependency Installation
# ═══════════════════════════════════════════════════════════════════════════════


def install_dependencies(
    workspace: Path,
    package_manager: str,
    strict: bool = False,
) -> bool:
    """Run the dependency installation command.

    Args:
        workspace: Path to project workspace
        package_manager: Detected package manager name
        strict: If True, raise on failure. If False (default), warn and continue.

    Returns:
        True if install succeeded, False if failed (only when strict=False)

    Raises:
        DependencyInstallError: If strict=True and installation fails
    """
    cmd = get_install_command(package_manager)

    if cmd is None:
        if strict:
            raise DependencyInstallError(package_manager, "Unknown package manager")
        return False

    try:
        result = subprocess.run(
            cmd,
            cwd=workspace,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            return True

        # Installation failed
        error_msg = result.stderr or result.stdout or "Unknown error"
        if strict:
            raise DependencyInstallError(package_manager, f"Command failed: {error_msg}")

        return False

    except FileNotFoundError:
        # Package manager not installed
        if strict:
            raise DependencyInstallError(
                package_manager,
                f"'{cmd[0]}' not found. Is {package_manager} installed?",
            )
        return False


def auto_install_dependencies(workspace: Path, strict: bool = False) -> bool:
    """Detect the package manager and install dependencies.

    Combine detection and installation as a convenience function.

    Args:
        workspace: Path to project workspace
        strict: If True, raise on failure. If False (default), warn and continue.

    Returns:
        True if install succeeded, False if failed or no package manager detected

    Raises:
        DependencyInstallError: If strict=True and installation fails
    """
    package_manager = detect_package_manager(workspace)

    if package_manager is None:
        if strict:
            raise DependencyInstallError("unknown", "No package manager detected")
        return False

    return install_dependencies(workspace, package_manager, strict=strict)
