# M007 — Provider Neutralization, Operator Truthfulness, and Legacy Claude Cleanup

## Goal
Transform SCC from "multi-provider in the main launch path" to "genuinely provider-neutral enterprise product."

## Architecture decisions (D029–D042)

| ID | Decision | Key point |
|----|----------|-----------|
| D030 | Canonical name | SCC — Sandboxed Code CLI |
| D032 | Fail-closed | Unknown providers raise, never fall back to Claude |
| D033 | Codex launch | `codex --dangerously-bypass-approvals-and-sandbox` in container |
| D034 | Registry placement | provider_registry.py, top-level composition module |
| D035 | Settings serialization | rendered_bytes, OCI writes verbatim |
| D036 | Persistence model | One volume per provider, full config dir |
| D037 | Auth readiness | Adapter-owned auth_check(), doctor integration |
| D038+D042 | Config freshness | SCC writes its own config layer deterministically on fresh launch |
| D039 | Runtime permissions | docker exec normalizes ownership/permissions on launch |
| D040 | Codex auth storage | Force cli_auth_credentials_store='file' in container |
| D041 | Config ownership | SCC uses provider-native layering, never overwrites user config |

## Config ownership model (D041 — the critical design point)

SCC does NOT own the provider's canonical config file. SCC owns only an SCC-managed injection layer using provider-native config precedence:

### Claude
- **SCC-owned:** `/home/agent/.claude/settings.json` — SCC-managed team/bundle settings
- **User-owned:** `/home/agent/.claude/settings.local.json` — user preferences (persists in volume)
- **Claude merges both** — SCC layer does not overwrite user layer
- **Auth:** `.credentials.json` in volume — persists across launches

### Codex
- **SCC-owned:** `/workspace/.codex/config.toml` — project-scoped config in workspace mount
  - Contains: cli_auth_credentials_store='file', sandbox/approval overrides, MCP servers from governed bundles
- **User-owned:** `/home/agent/.codex/config.toml` — user preferences (persists in volume)
  - Contains: model, personality, feature flags, agent definitions, project trust levels
- **Codex precedence:** CLI flags > profile > project config > user config > system > defaults
  - SCC's project config overrides user defaults without destroying them
- **Auth:** `auth.json` in volume — persists across launches

### Config freshness guarantee (D038+D042)
On every **fresh** launch, SCC deterministically writes the SCC-managed config layer — even when logically empty. This prevents stale team/workspace config from leaking. The user-level config in the volume is **never** modified by SCC.

On **resume**, SCC leaves existing config in place (matches original session).

### What persists in the provider volume (D036)
- Auth cache (Claude OAuth creds, Codex auth.json)
- User-level provider config (config.toml user preferences, settings.local.json)
- Provider state (history, transcripts, sessions, plugins, agents, rules)
- SCC state marker (.scc-provider-state.json)

### What is ephemeral
- SCC-managed config layer (written deterministically on each fresh launch)
- Claude: settings.json overwritten in volume via docker cp
- Codex: .codex/config.toml written in workspace mount (not volume)

### Permissions (D039)
- Build-time: Dockerfile sets config dirs to 0700, uid 1000
- Runtime: OCI launch normalizes permissions on every fresh launch
- Auth files: 0600, owned by agent

## ProviderRuntimeSpec (final)
```python
@dataclass(frozen=True)
class ProviderRuntimeSpec:
    provider_id: str
    display_name: str
    image_ref: str
    config_dir: str           # ".claude", ".codex"
    settings_path: str        # ".claude/settings.json", ".codex/config.toml" (SCC injection target)
    data_volume: str
```
No launch argv, auth fields. Launch argv is runner-owned. Auth is adapter-owned.

Note: `settings_path` for Codex is the project-scoped path (".codex/config.toml"), not the user-level path. For Claude it is ".claude/settings.json". The AgentRunner resolves this to the correct absolute container path based on workspace mount.

## AuthReadiness (D037)
```python
@dataclass(frozen=True)
class AuthReadiness:
    status: str  # "missing", "present"
    mechanism: str  # "oauth_file", "auth_json_file"
    guidance: str  # actionable next step
```
V1 checks file presence only. "validated" level deferred. Doctor wording: "auth cache present" not "logged in."

## State marker
`.scc-provider-state.json` in volume: `{provider_id, layout_version: 1, auth_storage_mode: "file"}`.
Enables future migrations, cross-provider collision detection, diagnostics.

## Scope boundary
- **In scope:** Settings-path fix, settings-format ownership, typed registry, fail-closed resolution, config freshness via native layering, runtime permission normalization, Codex auth storage, auth readiness checks, legacy constant cleanup, session/resume/doctor, product naming, image hardening.
- **Out of scope:** New providers, Desktop sandbox provider-awareness, marketplace rewrite, Podman, scc auth commands, fine-grained volume splitting, validated auth level.
