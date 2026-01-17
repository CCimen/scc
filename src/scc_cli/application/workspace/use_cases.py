from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from scc_cli.application.interaction_requests import ConfirmRequest
from scc_cli.core.errors import UsageError, WorkspaceNotFoundError
from scc_cli.core.workspace import ResolverResult
from scc_cli.ports.platform_probe import PlatformProbe
from scc_cli.services.workspace import (
    get_suspicious_reason,
    is_suspicious_directory,
    resolve_launch_context,
)

SUSPICIOUS_WARNING_ID = "workspace-suspicious"
WSL_WARNING_ID = "workspace-wsl-performance"


@dataclass(frozen=True)
class WorkspaceContext:
    """Workspace context resolved for launch or worktree flows.

    Invariants:
        - Resolution follows the same precedence rules as the CLI.
        - Paths are resolved and stable for session identity.

    Args:
        resolver_result: Raw resolver output with path and mount details.
    """

    resolver_result: ResolverResult

    @property
    def workspace_root(self) -> Path:
        """Workspace root (WR)."""
        return self.resolver_result.workspace_root

    @property
    def entry_dir(self) -> Path:
        """Entry directory (ED)."""
        return self.resolver_result.entry_dir

    @property
    def mount_root(self) -> Path:
        """Mount root (MR)."""
        return self.resolver_result.mount_root

    @property
    def container_workdir(self) -> str:
        """Container working directory (CW)."""
        return self.resolver_result.container_workdir

    @property
    def is_auto_detected(self) -> bool:
        """Whether the workspace was auto-detected."""
        return self.resolver_result.is_auto_detected

    @property
    def is_suspicious(self) -> bool:
        """Whether the workspace is considered suspicious."""
        return self.resolver_result.is_suspicious

    @property
    def is_mount_expanded(self) -> bool:
        """Whether the mount root was expanded for worktrees."""
        return self.resolver_result.is_mount_expanded

    @property
    def reason(self) -> str:
        """Debug explanation of the resolution path."""
        return self.resolver_result.reason

    @property
    def is_auto_eligible(self) -> bool:
        """Whether the workspace can be auto-launched without prompts."""
        return self.resolver_result.is_auto_eligible()


@dataclass(frozen=True)
class ResolveWorkspaceRequest:
    """Inputs for resolving workspace context.

    Invariants:
        - Resolution order is stable for git and .scc.yaml detection.
        - Paths are interpreted relative to the provided cwd.

    Args:
        cwd: Directory where the user invoked the command.
        workspace_arg: Explicit workspace argument, if provided.
        allow_suspicious: Whether explicit suspicious paths are allowed.
        include_git_dir_fallback: Whether to check for .git markers when git is unavailable.
    """

    cwd: Path
    workspace_arg: str | None
    allow_suspicious: bool = False
    include_git_dir_fallback: bool = False


@dataclass(frozen=True)
class WorkspaceWarning:
    """Warning details surfaced during workspace validation.

    Invariants:
        - Warning identifiers remain stable for UI adapters.
        - Messages mirror existing CLI prompts.

    Args:
        warning_id: Stable identifier for the warning.
        title: Short title used in warning panels.
        message: Main warning message text.
        suggestion: Optional follow-up hint for users.
        console_message: Text emitted to stderr when applicable.
        emit_stderr: Whether the warning should be written to stderr.
    """

    warning_id: str
    title: str
    message: str
    suggestion: str | None
    console_message: str
    emit_stderr: bool


@dataclass(frozen=True)
class WorkspaceValidationStep:
    """Validation step with optional confirmation request.

    Invariants:
        - ConfirmRequest prompts stay aligned with CLI confirmations.

    Args:
        warning: Warning metadata describing the issue.
        confirm_request: Optional request for user confirmation.
    """

    warning: WorkspaceWarning
    confirm_request: ConfirmRequest | None = None


@dataclass(frozen=True)
class WorkspaceValidationResult:
    """Validated workspace path plus warnings to surface at the edge.

    Invariants:
        - Steps are ordered in the sequence they should be displayed.

    Args:
        workspace_path: Resolved workspace path that passed validation.
        steps: Warning steps to render at the CLI/UI edge.
    """

    workspace_path: Path
    steps: tuple[WorkspaceValidationStep, ...]


def resolve_workspace(request: ResolveWorkspaceRequest) -> WorkspaceContext | None:
    """Resolve workspace context with unified precedence rules.

    Invariants:
        - Preserves existing resolution order and path canonicalization.
        - Does not emit UI output; callers render warnings separately.

    Args:
        request: Resolution inputs from CLI or UI flows.

    Returns:
        WorkspaceContext with resolved paths, or None if no workspace could be resolved.
    """
    result = resolve_launch_context(
        request.cwd,
        request.workspace_arg,
        allow_suspicious=request.allow_suspicious,
        include_git_dir_fallback=request.include_git_dir_fallback,
    )
    if result is None:
        return None
    return WorkspaceContext(result)


def validate_workspace(
    workspace: str | None,
    *,
    allow_suspicious: bool,
    interactive_allowed: bool,
    platform_probe: PlatformProbe,
) -> WorkspaceValidationResult | None:
    """Validate a workspace path and emit warning metadata.

    Invariants:
        - Suspicious workspace messaging matches CLI prompts.
        - WSL performance warnings are reported without UI side effects.

    Args:
        workspace: Workspace path string, or None when unset.
        allow_suspicious: Whether to allow suspicious paths without confirmation.
        interactive_allowed: Whether the UI may prompt for confirmation.
        platform_probe: Platform probe dependency for WSL checks.

    Returns:
        WorkspaceValidationResult or None when no workspace path is provided.

    Raises:
        WorkspaceNotFoundError: If the workspace path does not exist.
        UsageError: If a suspicious path is blocked in non-interactive mode.
    """
    if workspace is None:
        return None

    workspace_path = Path(workspace).expanduser().resolve()
    if not workspace_path.exists():
        raise WorkspaceNotFoundError(path=str(workspace_path))

    steps: list[WorkspaceValidationStep] = []

    if is_suspicious_directory(workspace_path):
        reason = get_suspicious_reason(workspace_path) or "Suspicious directory"
        warning = WorkspaceWarning(
            warning_id=SUSPICIOUS_WARNING_ID,
            title="Suspicious Workspace",
            message=reason,
            suggestion="Consider using a project-specific directory instead.",
            console_message=reason,
            emit_stderr=allow_suspicious,
        )
        if allow_suspicious:
            steps.append(WorkspaceValidationStep(warning=warning))
        elif interactive_allowed:
            steps.append(
                WorkspaceValidationStep(
                    warning=warning,
                    confirm_request=ConfirmRequest(
                        request_id="confirm-suspicious-workspace",
                        prompt="Continue anyway?",
                    ),
                )
            )
        else:
            raise UsageError(
                user_message=(
                    f"Refusing to start in suspicious directory: {workspace_path}\n  → {reason}"
                ),
                suggested_action=(
                    "Either:\n"
                    f"  • Run: scc start --allow-suspicious-workspace {workspace_path}\n"
                    "  • Run: scc start --interactive (to choose a different workspace)\n"
                    "  • Run from a project directory inside a git repository"
                ),
            )

    if platform_probe.is_wsl2():
        is_optimal, _warning = platform_probe.check_path_performance(workspace_path)
        if not is_optimal:
            warning = WorkspaceWarning(
                warning_id=WSL_WARNING_ID,
                title="Performance Warning",
                message="Your workspace is on the Windows filesystem.",
                suggestion="For better performance, move to ~/projects inside WSL.",
                console_message=(
                    "Workspace is on the Windows filesystem. Performance may be slow."
                ),
                emit_stderr=True,
            )
            confirm_request = (
                ConfirmRequest(
                    request_id="confirm-wsl-performance",
                    prompt="Continue anyway?",
                )
                if interactive_allowed
                else None
            )
            steps.append(
                WorkspaceValidationStep(
                    warning=warning,
                    confirm_request=confirm_request,
                )
            )

    return WorkspaceValidationResult(
        workspace_path=workspace_path,
        steps=_freeze_steps(steps),
    )


def _freeze_steps(steps: Iterable[WorkspaceValidationStep]) -> tuple[WorkspaceValidationStep, ...]:
    return tuple(steps)
