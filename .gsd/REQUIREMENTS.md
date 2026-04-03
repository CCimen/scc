# REQUIREMENTS.md

## Product requirements
- SCC must remain a governed runtime for coding agents and must not become a new general-purpose coding agent.
- V1 supports Claude Code and Codex as first-class providers.
- SCC core must be provider-neutral and runtime-portable.
- SCC must not require Docker Desktop.
- SCC must ship a plain OCI runtime path first and keep Podman on the same contracts.
- Network modes must be truthful and enforcement must live in runtime topology plus policy, not only in provider-native features.
- Only org and delegated team policy may widen effective egress.
- Project and user scopes may only narrow effective egress or emit request metadata.
- V1 enforced egress is HTTP/HTTPS only.
- Provider-core destinations are automatic and minimal for the selected provider only.
- GitHub, npm, PyPI, and other dev destinations must remain explicit org/team policy choices.
- The first cross-agent safety layer must govern destructive git plus explicit network tools.
- Runtime-level safety must fail closed when policy cannot be loaded or validated.
- Open Agent Skills are the only intended shared portability layer.
- Plugins, hooks, rules, and marketplaces remain provider-native integrations.

## Engineering requirements
- Use typed internal models for provider planning, runtime planning, network policy, and safety.
- Keep raw dictionaries only at parsing and serialization boundaries.
- Align error categories, exit codes, and human/JSON rendering early.
- Preserve current working behavior with characterization tests before large refactors.
- Re-enable size and complexity guardrails after the main launch/runtime seams are stabilized.
- Keep diagnostics honest about provider, runtime, network, and safety status.

## Quality bar
- Every milestone exits green on `uv run ruff check`, `uv run mypy src/scc_cli`, and `uv run pytest`.
- Security claims must be directly explainable to a skeptical enterprise reviewer.
- The codebase should become more typed, more modular, and easier to reason about after each milestone, not harder.
