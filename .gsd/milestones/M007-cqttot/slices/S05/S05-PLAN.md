# S05: Product naming, documentation truthfulness, and milestone validation

**Goal:** README says 'Sandboxed Code CLI'. pyproject.toml description is provider-neutral. Truthfulness guardrail tests cover M007 deliverables (ProviderRuntimeSpec, fail-closed dispatch, doctor provider-awareness, legacy constant cleanup).
**Demo:** After this: README says 'Sandboxed Code CLI'. D-001 updated. All user-facing strings consistent. Truthfulness guardrail expanded to cover M007 changes.

## Tasks
- [x] **T01: Updated README title to 'SCC - Sandboxed Code CLI', made pyproject.toml provider-neutral, added 5 M007 truthfulness guardrail tests** — Fix the product name in README.md and pyproject.toml per D030, then add ~5 truthfulness guardrail tests to test_docs_truthfulness.py covering M007 deliverables.

## Steps

1. Edit `README.md` line 1: change `SCC - Sandboxed Claude CLI` to `SCC - Sandboxed Code CLI`.
2. Edit `pyproject.toml` line 8 description: change `Run Claude Code in Docker sandboxes with team configs and git worktree support` to `Run AI coding agents in Docker sandboxes with team configs and git worktree support`.
3. Add an M007 section to `tests/test_docs_truthfulness.py` with these guardrail tests:
   - `test_readme_title_says_sandboxed_code_cli` — asserts README line 1 contains 'Sandboxed Code CLI', not 'Sandboxed Claude CLI' or 'Sandboxed Coding CLI'
   - `test_provider_runtime_spec_exists_in_core` — asserts `core/provider_registry.py` exists and contains `PROVIDER_REGISTRY` and `ProviderRuntimeSpec` is defined in `core/contracts.py`
   - `test_fail_closed_dispatch_error_exists` — asserts `core/errors.py` defines `InvalidProviderError`
   - `test_doctor_check_provider_auth_exists` — asserts `doctor/checks/environment.py` defines `check_provider_auth`
   - `test_core_constants_no_claude_specifics` — asserts `core/constants.py` does NOT contain claude-specific runtime constants (SANDBOX_IMAGE, AGENT_NAME, DATA_VOLUME etc). This complements the existing `test_no_claude_constants_in_core.py` guardrail but lives in the truthfulness test file for documentation continuity.
4. Run `uv run ruff check README.md tests/test_docs_truthfulness.py` — must pass.
5. Run `uv run pytest tests/test_docs_truthfulness.py -v` — all tests including new ones must pass.
6. Run `uv run pytest -q` — full suite must pass with zero regressions vs 4745 baseline.

## Must-Haves

- [ ] README title is 'SCC - Sandboxed Code CLI'
- [ ] pyproject.toml description is provider-neutral
- [ ] 5 new truthfulness tests in test_docs_truthfulness.py covering M007 deliverables
- [ ] Full test suite passes

## Verification

- `uv run ruff check` — zero errors
- `uv run pytest tests/test_docs_truthfulness.py tests/test_provider_branding.py -v` — all pass
- `uv run pytest -q` — >= 4750 passed, 0 failed
  - Estimate: 20m
  - Files: README.md, pyproject.toml, tests/test_docs_truthfulness.py
  - Verify: uv run pytest tests/test_docs_truthfulness.py tests/test_provider_branding.py -v && uv run ruff check && uv run pytest -q
- [x] **T02: Added workspace-scoped Codex settings path and git-exclude repo cleanliness for D041 config ownership layering** — Implement the config ownership model from D041. Current code builds settings under /home/agent using spec.settings_path. Codex SCC-managed config should use workspace-scoped .codex/config.toml (project-scoped), not home-level provider config. Handle repo cleanliness: ensure .codex is excluded/ignored safely without mutating tracked files unexpectedly. Add tests for repo cleanliness and expected behavior. Claude path (settings.json) should remain as-is.

Steps:
1. Read current _inject_settings and _build_agent_settings in OCI runtime and start_session
2. Update Codex settings path in ProviderRuntimeSpec to use workspace-scoped path
3. Update OCI runtime to handle workspace-scoped vs volume-scoped settings injection
4. Ensure .codex dir in workspace mount does not dirty user repos (add to .gitignore guidance or use ephemeral mount)
5. Add tests proving Codex config goes to workspace mount, Claude config goes to volume
6. Run full test suite
  - Estimate: 45m
  - Files: src/scc_cli/core/provider_registry.py, src/scc_cli/adapters/oci_sandbox_runtime.py, src/scc_cli/commands/launch/start_session.py, tests/test_provider_registry.py, tests/adapters/test_oci_sandbox_runtime.py
  - Verify: uv run pytest tests/test_provider_registry.py tests/adapters/test_oci_sandbox_runtime.py -v && uv run ruff check && uv run mypy src/scc_cli
- [ ] **T03: Implement D035: provider-owned settings serialization** — Refactor AgentSettings so the runner produces rendered bytes, not a dict. OCI runtime writes bytes verbatim without format assumption. AgentRunner.build_settings() becomes responsible for serialization (JSON for Claude, TOML for Codex).

Steps:
1. Read current AgentSettings model and its consumers
2. Change AgentSettings from content:dict to rendered_bytes:bytes + path:Path + suffix:str
3. Update ClaudeAgentRunner.build_settings() to serialize JSON
4. Update CodexAgentRunner.build_settings() to serialize TOML
5. Update OCI runtime _inject_settings to write rendered_bytes verbatim (remove json.dumps)
6. Add tests proving Claude renders JSON, Codex renders TOML, runtime no longer assumes JSON
7. Run full test suite
  - Estimate: 45m
  - Files: src/scc_cli/core/contracts.py, src/scc_cli/adapters/claude_agent_runner.py, src/scc_cli/adapters/codex_agent_runner.py, src/scc_cli/adapters/oci_sandbox_runtime.py, tests/adapters/test_claude_agent_runner.py, tests/adapters/test_codex_agent_runner.py, tests/adapters/test_oci_sandbox_runtime.py
  - Verify: uv run pytest tests/adapters/test_claude_agent_runner.py tests/adapters/test_codex_agent_runner.py tests/adapters/test_oci_sandbox_runtime.py -v && uv run ruff check && uv run mypy src/scc_cli
- [ ] **T04: Implement D033: Codex launch policy argv** — Current CodexAgentRunner still launches plain `codex`. D033 says launch with `codex --dangerously-bypass-approvals-and-sandbox` inside the SCC container. Implement or explicitly revise D033 if a different policy is correct. Keep runner-owned.

Steps:
1. Read current CodexAgentRunner.build_command()
2. Update build_command to include --dangerously-bypass-approvals-and-sandbox
3. Add tests proving the flag is present in command output
4. Verify existing tests still pass
5. Run full test suite
  - Estimate: 20m
  - Files: src/scc_cli/adapters/codex_agent_runner.py, tests/adapters/test_codex_agent_runner.py
  - Verify: uv run pytest tests/adapters/test_codex_agent_runner.py -v && uv run ruff check && uv run mypy src/scc_cli
- [ ] **T05: Implement D040: file-based Codex auth in containers** — Force cli_auth_credentials_store='file' in the SCC-managed Codex config layer. Ensure auth writes back to the persistent provider volume. Add tests.

Steps:
1. Read current Codex settings construction in CodexAgentRunner or start_session
2. Ensure cli_auth_credentials_store='file' is always set in the Codex config
3. Verify auth.json path is in the persistent volume mount
4. Add tests: presence of file-based auth config, auth persistence path in volume
5. Run full test suite
  - Estimate: 30m
  - Files: src/scc_cli/adapters/codex_agent_runner.py, src/scc_cli/commands/launch/start_session.py, tests/adapters/test_codex_agent_runner.py
  - Verify: uv run pytest tests/adapters/test_codex_agent_runner.py -v && uv run ruff check && uv run mypy src/scc_cli
- [ ] **T06: Implement D037: adapter-owned auth readiness checks** — Move auth readiness ownership to the provider adapter boundary. Doctor should consume provider-owned auth readiness results. Auth wording must stay truthful: 'auth cache present' not 'logged in'. Improve local readiness quality: file existence + non-empty content. Parseable JSON for JSON auth files.

Steps:
1. Read current check_provider_auth in doctor/checks
2. Add auth_check() method to AgentProvider protocol returning AuthReadiness
3. Implement in ClaudeAgentProvider and CodexAgentProvider
4. Update doctor check to consume adapter-owned result
5. Ensure truthful wording
6. Add tests for both providers, edge cases (empty file, missing file, corrupt file)
7. Run full test suite
  - Estimate: 40m
  - Files: src/scc_cli/ports/agent_provider.py, src/scc_cli/adapters/claude_agent_provider.py, src/scc_cli/adapters/codex_agent_provider.py, src/scc_cli/doctor/checks/environment.py, tests/adapters/test_claude_agent_provider.py, tests/adapters/test_codex_agent_provider.py, tests/doctor/test_environment_checks.py
  - Verify: uv run pytest tests/adapters/test_claude_agent_provider.py tests/adapters/test_codex_agent_provider.py tests/doctor/ -v && uv run ruff check && uv run mypy src/scc_cli
- [ ] **T07: Remove remaining active-launch Claude fallbacks (D032)** — Check and eliminate any remaining launch/runtime paths that still substitute Claude when provider wiring is missing or unknown. Active launch logic must not silently choose Claude if agent_provider is absent or provider identity is invalid. Missing provider wiring should surface a typed launch error.

Steps:
1. Search codebase for Claude fallback patterns in launch/runtime paths
2. Identify any silent substitutions (default='claude' in active logic, not read/migration boundaries)
3. Replace with typed errors (InvalidProviderError or ProviderNotReadyError)
4. Preserve read/migration defaults (SessionRecord, config read) per D032
5. Add tests for fail-closed behavior on missing/invalid provider
6. Run full test suite
  - Estimate: 30m
  - Files: src/scc_cli/commands/launch/start_session.py, src/scc_cli/commands/launch/dependencies.py, src/scc_cli/adapters/oci_sandbox_runtime.py, tests/commands/launch/test_start_session.py
  - Verify: uv run pytest tests/commands/launch/ tests/adapters/test_oci_sandbox_runtime.py -v && uv run ruff check && uv run mypy src/scc_cli
- [ ] **T08: Implement D038/D042: config freshness on every fresh launch** — On every fresh launch (not resume), SCC writes the SCC-managed config layer deterministically — even when logically empty. On resume, existing config is left in place. Scoped to SCC-owned config layers only.

Steps:
1. Read current OCI runtime fresh-launch vs resume paths
2. Ensure fresh launch always writes the SCC-managed config (even if empty/default)
3. Ensure resume does NOT overwrite config
4. Add tests: governed->standalone, teamA->teamB, settings->no-settings transitions
5. Run full test suite
  - Estimate: 35m
  - Files: src/scc_cli/adapters/oci_sandbox_runtime.py, src/scc_cli/commands/launch/start_session.py, tests/adapters/test_oci_sandbox_runtime.py, tests/commands/launch/test_start_session.py
  - Verify: uv run pytest tests/adapters/test_oci_sandbox_runtime.py tests/commands/launch/ -v && uv run ruff check && uv run mypy src/scc_cli
- [ ] **T09: Implement D039: runtime permission normalization** — Build-time Dockerfile permissions are not enough. Runtime launch must normalize mounted provider state permissions. Provider state dir 0700, auth files 0600, uid 1000 ownership. Scoped to provider state/auth paths only.

Steps:
1. Read current OCI runtime launch sequence
2. Add permission normalization step after container creation, before settings injection
3. Use docker exec to set ownership/permissions on provider config dir and auth files
4. Add tests for normalization command construction
5. Run full test suite
  - Estimate: 30m
  - Files: src/scc_cli/adapters/oci_sandbox_runtime.py, tests/adapters/test_oci_sandbox_runtime.py
  - Verify: uv run pytest tests/adapters/test_oci_sandbox_runtime.py -v && uv run ruff check && uv run mypy src/scc_cli
- [ ] **T10: Image hardening: scc-base and scc-agent-codex improvements** — scc-base should prepare both ~/.claude and ~/.codex with correct ownership/permissions. scc-agent-codex should pin Codex package version via ARG. Keep builds deterministic.

Steps:
1. Read current Dockerfile definitions in images/
2. Update scc-base to create both .claude and .codex dirs with 0700/uid1000
3. Update scc-agent-codex to use ARG for version pinning
4. Ensure doctor/build guidance matches actual image tags and build commands
5. Add integration tests for structural properties
6. Run test suite
  - Estimate: 25m
  - Files: images/scc-base/Dockerfile, images/scc-agent-codex/Dockerfile, tests/test_image_structure.py
  - Verify: uv run pytest tests/test_image_structure.py -v && uv run ruff check
- [ ] **T11: Persistence model tests: config freshness transitions** — Add targeted tests proving the persistence model works across session transitions: governed->standalone launch, team A->team B, settings->no-settings. Verify config freshness is deterministic and not reliant on fresh container creation alone.

Steps:
1. Identify the right test surface for persistence transitions
2. Write tests for governed->standalone (stale team config cleared)
3. Write tests for teamA->teamB (new team config replaces old)
4. Write tests for settings->no-settings (empty/default config written)
5. Run full test suite
  - Estimate: 30m
  - Files: tests/adapters/test_oci_sandbox_runtime.py, tests/commands/launch/test_start_session.py
  - Verify: uv run pytest tests/adapters/test_oci_sandbox_runtime.py tests/commands/launch/ -v && uv run ruff check
- [ ] **T12: Final truthfulness validation: decisions vs code reconciliation** — Verify that D033, D035, D037, D040, D041 are reflected in code and tests. Expand truthfulness guardrail tests to cover reconciliation items. Ensure README, docs, and UI naming are consistent with 'SCC — Sandboxed Code CLI'. Run milestone exit gate.

Steps:
1. Add truthfulness tests validating each reconciliation decision is implemented
2. Verify D033: Codex launch argv includes bypass flag
3. Verify D035: AgentSettings uses rendered_bytes, OCI runtime no json.dumps
4. Verify D037: AgentProvider has auth_check method
5. Verify D040: Codex config includes file-based auth store
6. Verify D041: Codex settings path is workspace-scoped
7. Run full test suite as exit gate
8. Verify test count >= 4750
  - Estimate: 30m
  - Files: tests/test_docs_truthfulness.py, tests/test_provider_branding.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest -q
