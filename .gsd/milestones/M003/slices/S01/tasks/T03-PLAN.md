---
estimated_steps: 25
estimated_files: 1
skills_used: []
---

# T03: Add guardrail test preventing stale detection calls and run full verification

## Description

Add a guardrail test that scans `src/scc_cli/` for direct `docker.check_docker_available()` calls outside the adapter layer, preventing future regression. Then run the full lint/type/test suite to confirm S01 is green.

## Steps

1. **Create `tests/test_runtime_detection_hotspots.py`** — Write a test that uses `pathlib` and text scanning to find `check_docker_available()` calls in `src/scc_cli/`. The test should:
   - Scan all `.py` files under `src/scc_cli/` recursively.
   - Find lines containing `check_docker_available` (as a function call or import).
   - Exclude allowed locations: `src/scc_cli/docker/core.py` (definition), `src/scc_cli/docker/__init__.py` (re-export), `src/scc_cli/adapters/docker_runtime_probe.py` (the adapter that wraps it).
   - Assert no other files contain the call. If violations are found, the error message should list the file and line number.
   - Follow the pattern established by `tests/test_launch_flow_hotspots.py` and `tests/test_no_root_sprawl.py` if they exist.

2. **Run full verification suite** — Execute all verification commands:
   - `uv run ruff check` — no lint violations across entire repo.
   - `uv run mypy src/scc_cli` — all code typed.
   - `uv run pytest --rootdir "$PWD" -q` — full suite green including the new guardrail.

3. **Verify the guardrail catches violations** — Temporarily add a `check_docker_available` reference in a test to confirm the guardrail would catch it, then remove it. (Or simply verify the test logic by reading it carefully.)

## Must-Haves

- [ ] `tests/test_runtime_detection_hotspots.py` exists and passes.
- [ ] Guardrail correctly excludes `docker/core.py`, `docker/__init__.py`, and `adapters/docker_runtime_probe.py`.
- [ ] `uv run ruff check` passes.
- [ ] `uv run mypy src/scc_cli` passes.
- [ ] `uv run pytest --rootdir "$PWD" -q` passes (full suite).

## Verification

- `uv run pytest tests/test_runtime_detection_hotspots.py -q` — guardrail passes.
- `uv run ruff check` — clean.
- `uv run mypy src/scc_cli` — clean.
- `uv run pytest --rootdir "$PWD" -q` — full suite green.

## Inputs

- `src/scc_cli/adapters/docker_sandbox_runtime.py`
- `src/scc_cli/adapters/docker_runtime_probe.py`
- `src/scc_cli/docker/core.py`
- `src/scc_cli/docker/__init__.py`

## Expected Output

- `tests/test_runtime_detection_hotspots.py`

## Verification

uv run pytest tests/test_runtime_detection_hotspots.py -q && uv run ruff check && uv run mypy src/scc_cli && uv run pytest --rootdir "$PWD" -q
