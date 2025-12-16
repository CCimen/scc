"""
Configuration management.
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Optional
from rich.console import Console


CONFIG_DIR = Path.home() / ".config" / "sundsvalls-claude"
CONFIG_FILE = CONFIG_DIR / "config.json"
SESSIONS_FILE = CONFIG_DIR / "sessions.json"


DEFAULT_CONFIG = {
    "version": "1.0.0",
    "organization": {
        "name": "Sundsvalls kommun",
        "github_org": "sundsvalls",
        "config_repo": "claude-code-base",
    },
    "workspace_base": "~/projects",
    "profiles": {
        "base": {
            "description": "Default profile for all teams",
            "tools": [],
            "repositories": [],
        },
        "java-wso2": {
            "description": "Java/Spring Boot/WSO2 development",
            "tools": ["java", "maven", "gradle"],
            "repositories": [],
        },
        "python-fastapi": {
            "description": "Python/FastAPI/Bun development",
            "tools": ["python", "pip", "poetry", "bun"],
            "repositories": [],
        },
        "react-nextjs": {
            "description": "React/Next.js frontend development",
            "tools": ["node", "npm", "pnpm"],
            "repositories": [],
        },
    },
    "git": {
        "protected_branches": ["main", "master", "develop", "production", "staging"],
        "branch_prefix": "claude/",
    },
    "docker": {
        "enabled": True,
        "fallback_to_native": False,
    },
}


def get_config_dir() -> Path:
    """Get the configuration directory."""
    return CONFIG_DIR


def get_config_file() -> Path:
    """Get the configuration file path."""
    return CONFIG_FILE


def load_config() -> dict:
    """Load configuration from file, or return defaults."""
    
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                user_config = json.load(f)
            
            # Merge with defaults
            config = DEFAULT_CONFIG.copy()
            deep_merge(config, user_config)
            return config
        except (json.JSONDecodeError, IOError):
            pass
    
    return DEFAULT_CONFIG.copy()


def save_config(config: dict):
    """Save configuration to file."""
    
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def init_config(console: Console):
    """Initialize configuration directory and files."""
    
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        console.print(f"[green]✓ Created config file: {CONFIG_FILE}[/green]")
    else:
        console.print(f"[green]✓ Config file exists: {CONFIG_FILE}[/green]")
    
    # Create sessions file
    if not SESSIONS_FILE.exists():
        with open(SESSIONS_FILE, "w") as f:
            json.dump({"sessions": []}, f)
        console.print(f"[green]✓ Created sessions file: {SESSIONS_FILE}[/green]")


def open_in_editor():
    """Open config file in default editor."""
    
    editor = os.environ.get("EDITOR", "nano")
    
    # Ensure config exists
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
    
    subprocess.run([editor, str(CONFIG_FILE)])


def deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base."""
    
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            deep_merge(base[key], value)
        else:
            base[key] = value
    
    return base


def get_team_config(team: str) -> Optional[dict]:
    """Get configuration for a specific team."""
    
    config = load_config()
    return config.get("profiles", {}).get(team)


def add_recent_workspace(workspace: str, team: Optional[str] = None):
    """Add a workspace to recent list."""
    
    try:
        if SESSIONS_FILE.exists():
            with open(SESSIONS_FILE) as f:
                data = json.load(f)
        else:
            data = {"sessions": []}
        
        from datetime import datetime
        
        # Remove existing entry for this workspace
        data["sessions"] = [s for s in data["sessions"] if s.get("workspace") != workspace]
        
        # Add new entry at the start
        data["sessions"].insert(0, {
            "workspace": workspace,
            "team": team,
            "last_used": datetime.now().isoformat(),
            "name": Path(workspace).name,
        })
        
        # Keep only last 20
        data["sessions"] = data["sessions"][:20]
        
        with open(SESSIONS_FILE, "w") as f:
            json.dump(data, f, indent=2)
    
    except (IOError, json.JSONDecodeError):
        pass


def get_recent_workspaces(limit: int = 10) -> list:
    """Get recent workspaces."""

    try:
        if SESSIONS_FILE.exists():
            with open(SESSIONS_FILE) as f:
                data = json.load(f)
            return data.get("sessions", [])[:limit]
    except (IOError, json.JSONDecodeError):
        pass

    return []


# ═══════════════════════════════════════════════════════════════════════════════
# Setup Wizard Support
# ═══════════════════════════════════════════════════════════════════════════════


def load_teams_config() -> dict:
    """
    Load teams/profiles configuration.

    Returns the full config with profiles section.
    Used by setup wizard for team selection.
    """
    return load_config()


def load_user_config() -> dict:
    """
    Load user-specific configuration.

    Returns merged config or defaults.
    Used by setup wizard to check setup state.
    """
    return load_config()


def save_user_config(user_config: dict) -> None:
    """
    Save user-specific configuration.

    Merges with existing config and saves.
    Used by setup wizard after configuration.
    """
    current = load_config()
    deep_merge(current, user_config)
    save_config(current)
