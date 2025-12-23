"""
Centralized JSON envelope kind names to prevent drift.

All JSON envelope `kind` values must be defined here as enum members.
This prevents inconsistencies like "TeamList" vs "TeamsList" across the codebase.

Usage:
    from scc_cli.kinds import Kind

    envelope = build_envelope(Kind.TEAM_LIST, data={...})
"""

from enum import Enum


class Kind(str, Enum):
    """JSON envelope kind identifiers.

    Uses str mixin so enum values serialize directly to JSON without .value.
    Add new kinds here to ensure consistency across all commands.
    """

    # Team commands
    TEAM_LIST = "TeamList"
    TEAM_INFO = "TeamInfo"
    TEAM_CURRENT = "TeamCurrent"
    TEAM_SWITCH = "TeamSwitch"

    # Status/Doctor
    STATUS = "Status"
    DOCTOR_REPORT = "DoctorReport"

    # Worktree commands
    WORKTREE_LIST = "WorktreeList"
    WORKTREE_CREATE = "WorktreeCreate"
    WORKTREE_REMOVE = "WorktreeRemove"

    # Session/Container
    SESSION_LIST = "SessionList"
    CONTAINER_LIST = "ContainerList"

    # Org admin
    ORG_VALIDATION = "OrgValidation"
    ORG_SCHEMA = "OrgSchema"

    # Support
    SUPPORT_BUNDLE = "SupportBundle"

    # Config
    CONFIG_EXPLAIN = "ConfigExplain"

    # Start
    START_DRY_RUN = "StartDryRun"

    # Init
    INIT_RESULT = "InitResult"
