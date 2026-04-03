# PROJECT.md

# Sandboxed Coding CLI (SCC)

## What the project is
SCC is a governed runtime for AI coding agents. It helps organizations run approved agents inside portable sandboxes with explicit policy, team-level configuration, safer defaults, and real runtime-enforced controls.

## What the project is not
- not a new general-purpose coding agent
- not a forever-Claude-only wrapper
- not a Docker Desktop-only product
- not a fake security story built on advisory naming
- not a proprietary skills ecosystem

## Current v1 product target
The v1 target is a clean architecture on top of `scc-sync-1.7.3` that supports Claude Code and Codex through the same provider-neutral core, portable OCI runtimes, enforced web egress, and a shared runtime safety engine.

## Strategic success condition
A security or platform team can approve SCC because its governance model, runtime enforcement, and diagnostics are understandable and inspectable, while developers can switch providers and team contexts without rebuilding their world.
