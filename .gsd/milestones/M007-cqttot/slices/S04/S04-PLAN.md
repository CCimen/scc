# S04: Legacy Claude path isolation and Docker module cleanup

**Goal:** Move Claude constants to docker/constants.py. Clean constants.py. Guardrail test enforces boundary.
**Demo:** After this: docker/core.py, docker/credentials.py, docker/launch.py use local Claude constants instead of shared imports. commands/profile.py documented as Claude-only. No shared constant import from constants.py for Claude runtime values anywhere in the codebase.

## Tasks
