---
estimated_steps: 32
estimated_files: 4
skills_used: []
---

# T02: Define ImageRef dataclass, SCC image constants, and Dockerfiles for scc-base and scc-agent-claude

## Description

Create the typed image contract layer and Dockerfiles that define what SCC provides in plain OCI mode. The OCI adapter (T03) and start_session image routing (T04) both consume these constants.

## Steps

1. Create `src/scc_cli/core/image_contracts.py` with:
   a. A frozen `ImageRef` dataclass with fields: `registry: str = ""`, `repository: str`, `tag: str = "latest"`, `digest: str | None = None`.
   b. A `full_ref()` method on `ImageRef` that returns the canonical `registry/repository:tag@digest` string (omitting empty components).
   c. An `image_ref(ref_string: str) -> ImageRef` parse helper that splits a Docker image reference string into the ImageRef fields. Handle common formats: `repo:tag`, `registry/repo:tag`, `registry/repo@sha256:...`, bare `repo` (implies `latest`).
   d. Constants: `SCC_BASE_IMAGE = ImageRef(repository="scc-base", tag="latest")` and `SCC_CLAUDE_IMAGE = ImageRef(repository="scc-agent-claude", tag="latest")`.
   e. A string constant `SCC_CLAUDE_IMAGE_REF = "scc-agent-claude:latest"` for use in SandboxSpec.image (which takes a plain string).
2. Create `images/scc-base/Dockerfile`:
   - `FROM ubuntu:22.04`
   - Install: git, curl, ca-certificates, jq
   - Create agent user: `useradd -m -u 1000 -s /bin/bash agent`
   - Create `/home/agent/.claude/` directory owned by agent
   - Set `USER agent` and `WORKDIR /home/agent`
3. Create `images/scc-agent-claude/Dockerfile`:
   - `FROM scc-base:latest`
   - Install Node.js 20 LTS (via NodeSource or nvm) as root, then switch to agent user
   - Install Claude CLI globally: `npm install -g @anthropic-ai/claude-code`
   - Verify: `claude --version` in a `RUN` step
   - Set `ENTRYPOINT ["/bin/bash"]` (the OCI adapter will exec claude explicitly)
4. Create `tests/test_image_contracts.py`:
   a. Test `ImageRef.full_ref()` for various combinations (with/without registry, digest).
   b. Test `image_ref()` parse helper for standard Docker reference formats.
   c. Test constants: `SCC_BASE_IMAGE.repository == "scc-base"`, `SCC_CLAUDE_IMAGE.repository == "scc-agent-claude"`.
5. Run `uv run pytest tests/test_image_contracts.py -q && uv run mypy src/scc_cli/core/image_contracts.py`.

## Must-Haves

- Frozen `ImageRef` dataclass with `full_ref()` method and `image_ref()` parser
- `SCC_BASE_IMAGE`, `SCC_CLAUDE_IMAGE`, `SCC_CLAUDE_IMAGE_REF` constants
- `images/scc-base/Dockerfile` with agent user (uid 1000), git, curl
- `images/scc-agent-claude/Dockerfile` building on scc-base with Node.js + Claude CLI
- Unit tests for ImageRef parsing and constants

## Inputs

- `src/scc_cli/core/contracts.py`
- `src/scc_cli/core/constants.py`

## Expected Output

- `src/scc_cli/core/image_contracts.py`
- `images/scc-base/Dockerfile`
- `images/scc-agent-claude/Dockerfile`
- `tests/test_image_contracts.py`

## Verification

uv run pytest tests/test_image_contracts.py -q && uv run mypy src/scc_cli/core/image_contracts.py
