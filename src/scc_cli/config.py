"""
Configuration management.

This module handles LOCAL user configuration only.
Organization config is fetched remotely (see remote.py).

Config structure:
- ~/.config/scc/config.json - User preferences and org source URL
- ~/.cache/scc/ - Cache directory (regenerable)

Migration from ~/.config/scc-cli/ to ~/.config/scc/ is handled automatically.
"""

import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from rich.console import Console

# ═══════════════════════════════════════════════════════════════════════════════
# XDG Base Directory Paths
# ═══════════════════════════════════════════════════════════════════════════════

# New config directory (XDG compliant)
CONFIG_DIR = Path.home() / ".config" / "scc"
CONFIG_FILE = CONFIG_DIR / "config.json"
SESSIONS_FILE = CONFIG_DIR / "sessions.json"

# Cache directory (regenerable, safe to delete)
CACHE_DIR = Path.home() / ".cache" / "scc"

# Legacy config directory (for migration)
LEGACY_CONFIG_DIR = Path.home() / ".config" / "scc-cli"


# ═══════════════════════════════════════════════════════════════════════════════
# User Config Defaults
# ═══════════════════════════════════════════════════════════════════════════════

USER_CONFIG_DEFAULTS = {
    "config_version": "1.0.0",
    "organization_source": None,  # Set during setup: {"url": "...", "auth": "..."}
    "selected_profile": None,
    "standalone": False,
    "cache": {
        "enabled": True,
        "ttl_hours": 24,
    },
    "hooks": {
        "enabled": False,
    },
    "overrides": {
        "workspace_base": "~/projects",
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# Path Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def get_config_dir() -> Path:
    """Get the configuration directory."""
    return CONFIG_DIR


def get_config_file() -> Path:
    """Get the configuration file path."""
    return CONFIG_FILE


def get_cache_dir() -> Path:
    """Get the cache directory path."""
    return CACHE_DIR


# ═══════════════════════════════════════════════════════════════════════════════
# Migration from scc-cli to scc
# ═══════════════════════════════════════════════════════════════════════════════


def migrate_config_if_needed() -> bool:
    """Migrate from legacy scc-cli directory to scc.

    Uses atomic swap pattern for safety:
    1. Create new structure in temp location
    2. Copy & transform
    3. Atomic rename (commit point)
    4. Preserve old directory (don't delete)

    Returns:
        True if migration was performed, False if already migrated or fresh install
    """
    # Already migrated - new config exists
    if CONFIG_DIR.exists():
        return False

    # Fresh install - no legacy config
    if not LEGACY_CONFIG_DIR.exists():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        return False

    # Create temp directory for atomic operation
    temp_dir = CONFIG_DIR.with_suffix(".tmp")

    try:
        temp_dir.mkdir(parents=True, exist_ok=True)

        # Copy all files from old to temp
        for item in LEGACY_CONFIG_DIR.iterdir():
            if item.is_file():
                shutil.copy2(item, temp_dir / item.name)
            elif item.is_dir():
                shutil.copytree(item, temp_dir / item.name)

        # Atomic rename (commit point)
        temp_dir.rename(CONFIG_DIR)

        return True

    except Exception:
        # Cleanup temp on failure, preserve old
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


# ═══════════════════════════════════════════════════════════════════════════════
# Deep Merge Utility
# ═══════════════════════════════════════════════════════════════════════════════


def deep_merge(base: dict, override: dict) -> dict:
    """
    Deep merge override into base.

    For nested dicts: recursive merge
    For non-dicts: override replaces base
    """
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            deep_merge(base[key], value)
        else:
            base[key] = value

    return base


def _deep_copy(d: dict) -> dict:
    """Create a deep copy of a dict (simple implementation for JSON-safe data)."""
    return json.loads(json.dumps(d))


# ═══════════════════════════════════════════════════════════════════════════════
# User Configuration Loading/Saving
# ═══════════════════════════════════════════════════════════════════════════════


def load_user_config() -> dict:
    """
    Load user configuration from ~/.config/scc/config.json.

    Returns merged config with defaults.
    """
    # Start with defaults
    config = _deep_copy(USER_CONFIG_DEFAULTS)

    # Ensure config dir exists
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # Load and merge user config if exists
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                user_config = json.load(f)
            deep_merge(config, user_config)
        except (OSError, json.JSONDecodeError):
            pass

    return config


def save_user_config(config: dict) -> None:
    """
    Save user configuration to ~/.config/scc/config.json.

    Args:
        config: Configuration dict to save
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


# ═══════════════════════════════════════════════════════════════════════════════
# Profile Selection
# ═══════════════════════════════════════════════════════════════════════════════


def get_selected_profile() -> str | None:
    """Get the currently selected profile name.

    Returns:
        Profile name string or None if not selected
    """
    config = load_user_config()
    return config.get("selected_profile")


def set_selected_profile(profile: str) -> None:
    """Set the selected profile.

    Args:
        profile: Profile name to select
    """
    config = load_user_config()
    config["selected_profile"] = profile
    save_user_config(config)


# ═══════════════════════════════════════════════════════════════════════════════
# Standalone Mode
# ═══════════════════════════════════════════════════════════════════════════════


def is_standalone_mode() -> bool:
    """Check if SCC is running in standalone mode (no organization).

    Returns:
        True if standalone mode is enabled
    """
    config = load_user_config()

    # Explicit standalone flag takes priority
    if config.get("standalone"):
        return True

    # Not standalone if organization_source is configured
    org_source = config.get("organization_source")
    if org_source and org_source.get("url"):
        return False

    return False


# ═══════════════════════════════════════════════════════════════════════════════
# Initialization
# ═══════════════════════════════════════════════════════════════════════════════


def init_config(console: Console) -> None:
    """Initialize configuration directory and files."""
    # Run migration if needed
    migrated = migrate_config_if_needed()
    if migrated:
        console.print(
            f"[yellow]⚠️  Migrated config from {LEGACY_CONFIG_DIR} to {CONFIG_DIR}[/]"
        )
        console.print("[dim]Old directory preserved. You may delete it manually.[/]")

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if not CONFIG_FILE.exists():
        # Save minimal user config
        save_user_config({"config_version": USER_CONFIG_DEFAULTS["config_version"]})
        console.print(f"[green]✓ Created config file: {CONFIG_FILE}[/green]")
    else:
        console.print(f"[green]✓ Config file exists: {CONFIG_FILE}[/green]")

    # Create sessions file
    if not SESSIONS_FILE.exists():
        with open(SESSIONS_FILE, "w") as f:
            json.dump({"sessions": []}, f)
        console.print(f"[green]✓ Created sessions file: {SESSIONS_FILE}[/green]")


def open_in_editor() -> None:
    """Open config file in default editor."""
    editor = os.environ.get("EDITOR", "nano")

    # Ensure config exists
    if not CONFIG_FILE.exists():
        save_user_config({"config_version": USER_CONFIG_DEFAULTS["config_version"]})

    subprocess.run([editor, str(CONFIG_FILE)])


# ═══════════════════════════════════════════════════════════════════════════════
# Session Management
# ═══════════════════════════════════════════════════════════════════════════════


def add_recent_workspace(workspace: str, team: str | None = None) -> None:
    """Add a workspace to recent list."""
    try:
        if SESSIONS_FILE.exists():
            with open(SESSIONS_FILE) as f:
                data = json.load(f)
        else:
            data = {"sessions": []}

        # Remove existing entry for this workspace
        data["sessions"] = [s for s in data["sessions"] if s.get("workspace") != workspace]

        # Add new entry at the start
        data["sessions"].insert(
            0,
            {
                "workspace": workspace,
                "team": team,
                "last_used": datetime.now().isoformat(),
                "name": Path(workspace).name,
            },
        )

        # Keep only last 20
        data["sessions"] = data["sessions"][:20]

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(SESSIONS_FILE, "w") as f:
            json.dump(data, f, indent=2)

    except (OSError, json.JSONDecodeError):
        pass


def get_recent_workspaces(limit: int = 10) -> list:
    """Get recent workspaces."""
    try:
        if SESSIONS_FILE.exists():
            with open(SESSIONS_FILE) as f:
                data = json.load(f)
            return data.get("sessions", [])[:limit]
    except (OSError, json.JSONDecodeError):
        pass

    return []


# ═══════════════════════════════════════════════════════════════════════════════
# Backward Compatibility Aliases
# ═══════════════════════════════════════════════════════════════════════════════

# These are kept for backward compatibility with existing code
# that imports from config module


def load_config() -> dict:
    """Alias for load_user_config (backward compatibility)."""
    return load_user_config()


def save_config(config: dict) -> None:
    """Alias for save_user_config (backward compatibility)."""
    save_user_config(config)


def get_team_config(team: str) -> dict | None:
    """Get configuration for a specific team (stub for compatibility).

    Note: Team config now comes from remote org config, not local config.
    This function is kept for backward compatibility but returns None.
    Use profiles.py for team/profile resolution.
    """
    return None


def list_available_teams() -> list[str]:
    """List available team profile names (stub for compatibility).

    Note: Teams now come from remote org config, not local config.
    This function is kept for backward compatibility but returns empty list.
    Use profiles.py for team/profile listing.
    """
    return []


# ═══════════════════════════════════════════════════════════════════════════════
# Legacy aliases (deprecated - will be removed in future versions)
# ═══════════════════════════════════════════════════════════════════════════════

# These constants are kept for backward compatibility only
INTERNAL_DEFAULTS = USER_CONFIG_DEFAULTS
DEFAULT_CONFIG = USER_CONFIG_DEFAULTS.copy()


def load_org_config() -> dict | None:
    """Deprecated: Org config is now fetched remotely.

    Use remote.load_org_config() instead.
    """
    return None


def save_org_config(org_config: dict) -> None:
    """Deprecated: Org config is now remote.

    This function is a no-op for backward compatibility.
    """
    pass


def is_organization_configured() -> bool:
    """Check if an organization source is configured.

    Returns True if organization_source URL is set.
    """
    config = load_user_config()
    org_source = config.get("organization_source")
    return bool(org_source and org_source.get("url"))


def get_organization_name() -> str | None:
    """Get organization name (deprecated).

    Note: Organization name now comes from remote org config.
    Returns None - use remote.load_org_config() instead.
    """
    return None


def load_teams_config() -> dict:
    """Alias for load_user_config (backward compatibility)."""
    return load_user_config()
