# M007-cqttot: Provider Neutralization, Operator Truthfulness, and Legacy Claude Cleanup

## Vision
SCC stops leaking Claude assumptions through shared/core/operator paths. ProviderRuntimeSpec model replaces scattered dicts. Settings serialization is provider-owned (JSON for Claude, TOML for Codex). SCC uses provider-native config layering to inject managed settings without overwriting user config — Claude settings.json is SCC-owned, Codex project-scoped .codex/config.toml is SCC-owned, user-level config in the persistent volume is never touched. Unknown providers fail closed. Config freshness is deterministic on every fresh launch. Auth persistence is intentional with runtime permission normalization and file-based Codex auth. Doctor separates backend, image, and auth readiness. Product naming is consistent. Legacy Claude paths are isolated.

## Slice Overview
| ID | Slice | Risk | Depends | Done | After this |
|----|-------|------|---------|------|------------|
| S01 | ProviderRuntimeSpec model, fail-closed dispatch, and settings-path fix | high | — | ✅ | ProviderRuntimeSpec defined in core/contracts.py. PROVIDER_REGISTRY in dependencies.py with get_runtime_spec() fail-closed lookup. _build_agent_settings uses spec.settings_path. Unknown provider_id raises InvalidProviderError. Full test suite passes. |
| S02 | Session, resume, and machine-readable output provider hardening | medium | S01 | ✅ | sessions.get_claude_sessions_dir renamed to provider-parameterized helper. audit.py derives path from provider. sandbox.py records provider_id='claude'. Quick Resume shows provider_id. Session list CLI displays provider column. |
| S03 | Doctor provider-awareness and typed provider errors | medium | S01 | ✅ | scc doctor --provider codex checks Codex readiness specifically. Doctor output groups backend health vs provider readiness. ProviderNotReadyError and ProviderImageMissingError exist with user_message and suggested_action. |
| S04 | Legacy Claude path isolation and Docker module cleanup | medium | S01 | ⬜ | docker/core.py, docker/credentials.py, docker/launch.py use local Claude constants instead of shared imports. commands/profile.py documented as Claude-only. No shared constant import from constants.py for Claude runtime values anywhere in the codebase. |
| S05 | Product naming, documentation truthfulness, and milestone validation | low | S01, S02, S03, S04 | ⬜ | README says 'Sandboxed Code CLI'. D-001 updated. All user-facing strings consistent. Truthfulness guardrail expanded to cover M007 changes. |
