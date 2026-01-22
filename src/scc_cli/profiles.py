"""
Profile resolution and marketplace URL logic.

Renamed from teams.py to better reflect profile resolution responsibilities.
Supports multi-marketplace architecture with org/team/project inheritance.

Key features:
- HTTPS-only enforcement: All marketplace URLs must use HTTPS protocol.
- Config inheritance: 3-layer merge (org defaults -> team -> project)
- Security boundaries: Blocked items (fnmatch patterns) never allowed
- Delegation control: Org controls whether teams can delegate to projects

Compatibility wrapper for scc_cli.application.profiles.
"""

from __future__ import annotations

from scc_cli.application import compute_effective_config as compute_effective_config_module
from scc_cli.application import profiles as profiles_module

BlockedItem = compute_effective_config_module.BlockedItem
ConfigDecision = compute_effective_config_module.ConfigDecision
DelegationDenied = compute_effective_config_module.DelegationDenied
EffectiveConfig = compute_effective_config_module.EffectiveConfig
MCPServer = compute_effective_config_module.MCPServer
SessionConfig = compute_effective_config_module.SessionConfig
StdioValidationResult = compute_effective_config_module.StdioValidationResult
compute_effective_config = compute_effective_config_module.compute_effective_config
is_allowed = compute_effective_config_module.is_plugin_allowed
is_mcp_allowed = compute_effective_config_module.is_mcp_allowed
is_project_delegated = compute_effective_config_module.is_project_delegated
is_team_delegated_for_mcp = compute_effective_config_module.is_team_delegated_for_mcp
is_team_delegated_for_plugins = compute_effective_config_module.is_team_delegated_for_plugins
matches_blocked = compute_effective_config_module.matches_blocked
mcp_candidates = compute_effective_config_module.mcp_candidates
validate_stdio_server = compute_effective_config_module.validate_stdio_server

list_profiles = profiles_module.list_profiles
resolve_profile = profiles_module.resolve_profile
resolve_marketplace = profiles_module.resolve_marketplace
get_marketplace_url = profiles_module.get_marketplace_url
_normalize_repo_path = profiles_module._normalize_repo_path
