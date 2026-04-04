---
estimated_steps: 54
estimated_files: 7
skills_used: []
---

# T01: CodexAgentRunner adapter, Codex image contracts, and Dockerfile

---
estimated_steps: 5
estimated_files: 6
skills_used: []
---

# T01: CodexAgentRunner adapter, Codex image contracts, and Dockerfile

**Slice:** S02 — CodexAgentRunner, provider-aware image selection, and launch path wiring
**Milestone:** M006-d622bc

## Description

Create the CodexAgentRunner adapter, add Codex image constants, create the Codex Dockerfile, and register the runner in bootstrap and fakes. This is the foundation — downstream tasks depend on this runner and image ref existing.

## Steps

1. Create `src/scc_cli/adapters/codex_agent_runner.py` mirroring `claude_agent_runner.py`. Key differences:
   - `DEFAULT_SETTINGS_PATH = Path("/home/agent/.codex/config.toml")` (Codex uses `.codex/` config dir)
   - `build_command` returns `argv=["codex"]` (no `--dangerously-skip-permissions` — that's Claude-specific)
   - `describe` returns `"Codex"`

2. Add Codex image constants to `src/scc_cli/core/image_contracts.py`:
   - `SCC_CODEX_IMAGE = ImageRef(repository="scc-agent-codex", tag="latest")`
   - `SCC_CODEX_IMAGE_REF = "scc-agent-codex:latest"`

3. Create `images/scc-agent-codex/Dockerfile` based on `images/scc-agent-claude/Dockerfile`. Install Node.js 20 LTS + `@openai/codex` via npm. Verify with `codex --version`. Same user/workdir pattern.

4. Add `codex_agent_runner: AgentRunner | None = None` field to `DefaultAdapters` in `src/scc_cli/bootstrap.py` (use `| None = None` default per KNOWLEDGE.md pattern). Instantiate `CodexAgentRunner()` in `get_default_adapters()`. Import `CodexAgentRunner` at the top.

5. Add `codex_agent_runner=FakeAgentRunner()` to `build_fake_adapters()` in `tests/fakes/__init__.py`. Also add `FakeAgentRunner()` to any inline `DefaultAdapters()` constructions in test files (grep for them).

6. Create `tests/test_codex_agent_runner.py` with the canonical 4-test shape per KNOWLEDGE.md:
   - `test_build_settings_returns_codex_path` — settings path is `/home/agent/.codex/config.toml`
   - `test_build_command_returns_codex_argv` — argv starts with `"codex"`, no `--dangerously-skip-permissions`
   - `test_describe_returns_codex` — returns `"Codex"`
   - `test_env_is_clean_str_to_str` — env dict is empty (D003 contract guard)
   Add Codex runner to `tests/contracts/test_agent_runner_contract.py` alongside Claude.

## Must-Haves

- [ ] CodexAgentRunner implements AgentRunner protocol with codex argv, .codex settings path, and "Codex" describe
- [ ] SCC_CODEX_IMAGE and SCC_CODEX_IMAGE_REF exist in image_contracts.py
- [ ] images/scc-agent-codex/Dockerfile installs Node.js 20 + @openai/codex
- [ ] codex_agent_runner field added to DefaultAdapters with None default
- [ ] FakeAgentRunner() wired into build_fake_adapters() for codex_agent_runner
- [ ] 4+ tests pass for CodexAgentRunner, contract test covers both runners

## Verification

- `uv run pytest tests/test_codex_agent_runner.py tests/contracts/test_agent_runner_contract.py -v` — all pass
- `uv run ruff check src/scc_cli/adapters/codex_agent_runner.py src/scc_cli/core/image_contracts.py src/scc_cli/bootstrap.py` — clean
- `uv run mypy src/scc_cli/adapters/codex_agent_runner.py src/scc_cli/core/image_contracts.py src/scc_cli/bootstrap.py` — no issues
- `uv run pytest --rootdir "$PWD" -q` — full suite, zero regressions

## Inputs

- `src/scc_cli/adapters/claude_agent_runner.py` — template for the new runner
- `src/scc_cli/core/image_contracts.py` — add Codex constants alongside Claude
- `images/scc-agent-claude/Dockerfile` — template for Codex Dockerfile
- `src/scc_cli/bootstrap.py` — add codex_agent_runner field and instantiation
- `tests/fakes/__init__.py` — add codex_agent_runner to build_fake_adapters
- `tests/contracts/test_agent_runner_contract.py` — extend with Codex runner

## Expected Output

- `src/scc_cli/adapters/codex_agent_runner.py` — new CodexAgentRunner adapter
- `src/scc_cli/core/image_contracts.py` — SCC_CODEX_IMAGE + SCC_CODEX_IMAGE_REF added
- `images/scc-agent-codex/Dockerfile` — new Codex container image definition
- `src/scc_cli/bootstrap.py` — codex_agent_runner field and wiring
- `tests/fakes/__init__.py` — codex_agent_runner in fake adapters
- `tests/test_codex_agent_runner.py` — new 4-test file
- `tests/contracts/test_agent_runner_contract.py` — Codex runner contract test added

## Inputs

- `src/scc_cli/adapters/claude_agent_runner.py`
- `src/scc_cli/core/image_contracts.py`
- `images/scc-agent-claude/Dockerfile`
- `src/scc_cli/bootstrap.py`
- `tests/fakes/__init__.py`
- `tests/contracts/test_agent_runner_contract.py`

## Expected Output

- `src/scc_cli/adapters/codex_agent_runner.py`
- `src/scc_cli/core/image_contracts.py`
- `images/scc-agent-codex/Dockerfile`
- `src/scc_cli/bootstrap.py`
- `tests/fakes/__init__.py`
- `tests/test_codex_agent_runner.py`
- `tests/contracts/test_agent_runner_contract.py`

## Verification

uv run pytest tests/test_codex_agent_runner.py tests/contracts/test_agent_runner_contract.py -v && uv run ruff check src/scc_cli/adapters/codex_agent_runner.py src/scc_cli/core/image_contracts.py src/scc_cli/bootstrap.py && uv run mypy src/scc_cli/adapters/codex_agent_runner.py src/scc_cli/core/image_contracts.py src/scc_cli/bootstrap.py && uv run pytest --rootdir "$PWD" -q
