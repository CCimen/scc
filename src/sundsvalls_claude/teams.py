"""
Team profile management.

Fetches team-specific configurations from GitHub or local config.
"""

import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Optional, List
import json


def list_teams(cfg: dict) -> List[dict]:
    """List available teams from configuration."""

    profiles = cfg.get("profiles", {})

    teams = []
    for name, info in profiles.items():
        teams.append({
            "name": name,
            "description": info.get("description", ""),
            "tools": info.get("tools", []),
            "repositories": info.get("repositories", []),
        })

    return teams


def get_team_details(team: str, cfg: dict) -> Optional[dict]:
    """
    Get detailed information for a specific team.

    Returns None if team doesn't exist.
    """
    profiles = cfg.get("profiles", {})
    team_info = profiles.get(team)

    if not team_info:
        return None

    return {
        "name": team,
        "description": team_info.get("description", ""),
        "tools": team_info.get("tools", []),
        "repositories": team_info.get("repositories", []),
        "settings": team_info.get("settings", {}),
        "claude_md": team_info.get("claude_md"),
    }


def fetch_team_config(team: str, cfg: dict) -> dict:
    """
    Fetch team-specific configuration.
    
    First checks local config, then tries to fetch from GitHub if configured.
    """
    
    # Check local config first
    local_config = cfg.get("profiles", {}).get(team)
    
    if local_config:
        return local_config
    
    # Try fetching from GitHub
    org_config = cfg.get("organization", {})
    github_org = org_config.get("github_org")
    config_repo = org_config.get("config_repo")
    
    if github_org and config_repo:
        return fetch_from_github(github_org, config_repo, team)
    
    # Return empty config
    return {"tools": [], "repositories": []}


def fetch_from_github(org: str, repo: str, team: str) -> dict:
    """
    Fetch team configuration from GitHub repository.
    
    Looks for profiles/{team}/config.json in the repository.
    """
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Sparse checkout just the team folder
            subprocess.run(
                [
                    "git", "clone",
                    "--depth", "1",
                    "--filter=blob:none",
                    "--sparse",
                    f"https://github.com/{org}/{repo}.git",
                    tmpdir,
                ],
                capture_output=True,
                timeout=30,
            )
            
            subprocess.run(
                ["git", "-C", tmpdir, "sparse-checkout", "set", f"profiles/{team}"],
                capture_output=True,
                timeout=10,
            )
            
            config_path = Path(tmpdir) / "profiles" / team / "config.json"
            
            if config_path.exists():
                with open(config_path) as f:
                    return json.load(f)
    
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, IOError):
        pass
    
    return {"tools": [], "repositories": []}


def apply_team_config(workspace: Path, team_config: dict):
    """
    Apply team configuration to a workspace.
    
    This copies CLAUDE.md, settings.json, and skills to the workspace.
    """
    
    if not workspace or not workspace.exists():
        return
    
    # Paths
    claude_dir = workspace / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    
    # Apply settings if present in team config
    if "settings" in team_config:
        settings_path = claude_dir / "settings.json"
        
        if not settings_path.exists():
            with open(settings_path, "w") as f:
                json.dump(team_config["settings"], f, indent=2)
    
    # Apply CLAUDE.md if present
    if "claude_md" in team_config:
        claude_md_path = workspace / "CLAUDE.md"
        
        if not claude_md_path.exists():
            claude_md_path.write_text(team_config["claude_md"])


def get_team_repositories(team: str, cfg: dict) -> List[dict]:
    """Get list of repositories for a team."""
    
    team_config = cfg.get("profiles", {}).get(team, {})
    return team_config.get("repositories", [])


def add_team_repository(team: str, repo: dict, cfg: dict) -> bool:
    """Add a repository to a team's list."""
    
    from . import config as cfg_module
    
    if team not in cfg.get("profiles", {}):
        return False
    
    cfg["profiles"][team].setdefault("repositories", []).append(repo)
    cfg_module.save_config(cfg)
    
    return True


def sync_team_from_github(team: str, cfg: dict) -> bool:
    """
    Sync team configuration from GitHub.
    
    Downloads the latest configuration and updates local config.
    """
    
    org_config = cfg.get("organization", {})
    github_org = org_config.get("github_org")
    config_repo = org_config.get("config_repo")
    
    if not github_org or not config_repo:
        return False
    
    team_config = fetch_from_github(github_org, config_repo, team)
    
    if team_config:
        from . import config as cfg_module
        
        cfg["profiles"][team] = team_config
        cfg_module.save_config(cfg)
        return True
    
    return False
