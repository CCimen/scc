"""
Typed exceptions for SCC - Sandboxed Claude CLI.

Error handling philosophy: "One message, one action"
- Each error has a clear user_message (what went wrong)
- Each error has a suggested_action (what to do next)
- Debug context is available with --debug flag

Exit codes:
- 0: Success
- 2: Invalid usage / bad input
- 3: Missing prerequisites (Docker, Git)
- 4: External tool failure (docker/git command failed)
- 5: Internal error (bug)
"""

from dataclasses import dataclass, field


@dataclass
class SCCError(Exception):
    """Base error with user-friendly messaging."""

    user_message: str
    suggested_action: str = ""
    debug_context: str | None = None
    exit_code: int = 1

    def __str__(self) -> str:
        return self.user_message


@dataclass
class UsageError(SCCError):
    """Invalid usage or bad input."""

    exit_code: int = field(default=2, init=False)


@dataclass
class PrerequisiteError(SCCError):
    """Docker/Git missing or wrong version."""

    exit_code: int = field(default=3, init=False)


@dataclass
class DockerNotFoundError(PrerequisiteError):
    """Docker is not installed or not in PATH."""

    user_message: str = field(default="Docker is not installed or not in PATH")
    suggested_action: str = field(
        default="Install Docker Desktop from https://docker.com/products/docker-desktop"
    )


@dataclass
class DockerVersionError(PrerequisiteError):
    """Docker version is too old for sandbox feature."""

    current_version: str = ""
    required_version: str = "4.50.0"
    user_message: str = field(default="")
    suggested_action: str = field(
        default="Update Docker Desktop from https://docker.com/products/docker-desktop"
    )

    def __post_init__(self) -> None:
        if not self.user_message:
            self.user_message = (
                f"Docker Desktop {self.required_version}+ required for sandbox support\n"
                f"Current: {self.current_version or 'unknown'} | Required: {self.required_version}+"
            )


@dataclass
class SandboxNotAvailableError(PrerequisiteError):
    """Docker sandbox feature is not available."""

    user_message: str = field(default="Docker sandbox feature is not available")
    suggested_action: str = field(
        default="Ensure Docker Desktop is version 4.50+ and sandbox feature is enabled"
    )


@dataclass
class GitNotFoundError(PrerequisiteError):
    """Git is not installed or not in PATH."""

    user_message: str = field(default="Git is not installed or not in PATH")
    suggested_action: str = field(default="Install Git from https://git-scm.com/downloads")


@dataclass
class ToolError(SCCError):
    """External tool (Docker/Git) command failed."""

    exit_code: int = field(default=4, init=False)
    command: str | None = None
    stderr: str | None = None

    def __post_init__(self) -> None:
        if self.command or self.stderr:
            parts = []
            if self.command:
                parts.append(f"Command: {self.command}")
            if self.stderr:
                parts.append(f"Error: {self.stderr}")
            self.debug_context = "\n".join(parts)


@dataclass
class WorkspaceError(ToolError):
    """Invalid workspace path or clone failed."""

    user_message: str = field(default="Workspace error")


@dataclass
class WorkspaceNotFoundError(WorkspaceError):
    """Workspace path does not exist."""

    path: str = ""
    user_message: str = field(default="")
    suggested_action: str = field(default="Check the path exists or create the directory")

    def __post_init__(self) -> None:
        super().__post_init__()
        if not self.user_message and self.path:
            self.user_message = f"Workspace not found: {self.path}"


@dataclass
class NotAGitRepoError(WorkspaceError):
    """Path is not a git repository."""

    path: str = ""
    user_message: str = field(default="")
    suggested_action: str = field(default="Initialize git with 'git init' or clone a repository")

    def __post_init__(self) -> None:
        super().__post_init__()
        if not self.user_message and self.path:
            self.user_message = f"Not a git repository: {self.path}"


@dataclass
class CloneError(WorkspaceError):
    """Git clone failed."""

    url: str = ""
    user_message: str = field(default="")
    suggested_action: str = field(default="Check the repository URL and your network connection")

    def __post_init__(self) -> None:
        super().__post_init__()
        if not self.user_message and self.url:
            self.user_message = f"Failed to clone repository: {self.url}"


@dataclass
class GitWorktreeError(ToolError):
    """Worktree creation/cleanup failed."""

    user_message: str = field(default="Git worktree operation failed")


@dataclass
class WorktreeExistsError(GitWorktreeError):
    """Worktree already exists."""

    path: str = ""
    user_message: str = field(default="")
    suggested_action: str = field(
        default="Use existing worktree, remove it first, or choose a different name"
    )

    def __post_init__(self) -> None:
        super().__post_init__()
        if not self.user_message and self.path:
            self.user_message = f"Worktree already exists: {self.path}"


@dataclass
class WorktreeCreationError(GitWorktreeError):
    """Failed to create worktree."""

    name: str = ""
    user_message: str = field(default="")
    suggested_action: str = field(
        default="Check if the branch already exists or if there are uncommitted changes"
    )

    def __post_init__(self) -> None:
        super().__post_init__()
        if not self.user_message and self.name:
            self.user_message = f"Failed to create worktree: {self.name}"


@dataclass
class SandboxLaunchError(ToolError):
    """Docker sandbox failed to start."""

    exit_code: int = field(default=5, init=False)
    user_message: str = field(default="Failed to start Docker sandbox")
    suggested_action: str = field(
        default="Check Docker Desktop is running and has available resources"
    )


@dataclass
class ContainerNotFoundError(ToolError):
    """Container does not exist (for resume operations)."""

    container_name: str = ""
    user_message: str = field(default="")
    suggested_action: str = field(
        default="Start a new session or check 'scc list' for available containers"
    )

    def __post_init__(self) -> None:
        super().__post_init__()
        if not self.user_message and self.container_name:
            self.user_message = f"Container not found: {self.container_name}"


@dataclass
class InternalError(SCCError):
    """Internal error (bug in the CLI)."""

    exit_code: int = field(default=5, init=False)
    suggested_action: str = field(
        default="Please report this issue at https://github.com/CCimen/scc/issues"
    )


@dataclass
class ConfigError(SCCError):
    """Configuration error."""

    exit_code: int = field(default=2, init=False)
    user_message: str = field(default="Configuration error")
    suggested_action: str = field(default="Run 'scc config --show' to view current configuration")


@dataclass
class ProfileNotFoundError(ConfigError):
    """Team profile not found."""

    profile_name: str = ""
    user_message: str = field(default="")
    suggested_action: str = field(default="Run 'scc team list' to see available profiles")

    def __post_init__(self) -> None:
        if not self.user_message and self.profile_name:
            self.user_message = f"Team profile not found: {self.profile_name}"


@dataclass
class PolicyViolationError(ConfigError):
    """Security policy violation during config processing.

    Raised when a plugin, MCP server, or other item is blocked by
    organization security policies.
    """

    item: str = ""
    blocked_by: str = ""
    item_type: str = "plugin"  # Default to plugin
    user_message: str = field(default="")
    suggested_action: str = field(default="")

    def __post_init__(self) -> None:
        if not self.user_message and self.item:
            if self.blocked_by:
                self.user_message = (
                    f"Security policy violation: '{self.item}' is blocked "
                    f"by pattern '{self.blocked_by}'"
                )
            else:
                self.user_message = f"Security policy violation: '{self.item}' is blocked"

        # Generate fix-it command for suggested action
        if not self.suggested_action and self.item:
            from scc_cli.utils.fixit import generate_policy_exception_command

            cmd = generate_policy_exception_command(self.item, self.item_type)
            self.suggested_action = f"To request a policy exception (requires PR approval): {cmd}"
