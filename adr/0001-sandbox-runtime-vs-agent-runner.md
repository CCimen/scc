# ADR 0001: Split SandboxRuntime and AgentRunner

Date: 2026-01-17
Status: Accepted

## Context
- SCC’s launch flow needs both sandbox lifecycle control and agent settings rendering.
- Docker and Claude format concerns were intertwined, making testing and reuse difficult.
- The refactor introduces `ports/` + `adapters/` and a `bootstrap.py` composition root.

## Decision
- Keep `SandboxRuntime` focused on sandbox lifecycle and status using domain types:
  - `SandboxSpec`, `SandboxHandle`, `SandboxStatus`.
- Keep `AgentRunner` focused on producing agent execution artifacts:
  - `AgentCommand`, `AgentSettings`.
- Use `bootstrap.py` to wire default adapters:
  - `DockerSandboxRuntime` for `SandboxRuntime`.
  - `ClaudeAgentRunner` for `AgentRunner`.
- Orchestrate the two in application use cases (e.g., `StartSession`).

## Consequences
- Clearer boundaries and easier unit testing via fake runtimes/runners.
- Docker lifecycle changes no longer affect Claude settings rendering (and vice versa).
- Future runtimes (Podman, remote runners) can implement `SandboxRuntime` without changing `AgentRunner`.
