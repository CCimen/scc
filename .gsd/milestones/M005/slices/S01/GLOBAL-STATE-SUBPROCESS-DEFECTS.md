# Global Mutable State and Subprocess Handling Defects

> Catalog produced by T04 (M005/S01). Covers all `src/scc_cli/**/*.py` files.
> Severity: 🔴 high (data corruption / hang risk), 🟡 medium (silent failure / test pollution), 🟢 low (style / hardening opportunity).

---

## 1. Global Mutable State

### 1a. Module-level singletons with `global` keyword mutation

| # | File | Line | Name | Pattern | Severity | Notes |
|---|------|------|------|---------|----------|-------|
| G01 | `console.py` | 417–418 | `_console`, `_err_console` | `None` → lazy `Console()` via `global` | 🟡 medium | Mutated by `get_console()`, `get_err_console()`, `reset_consoles()`. No thread safety. `reset_consoles()` is test-only but has no guard. |
| G02 | `theme.py` | 279 | `_theme_instance` | `None` → lazy `Theme()` via `global` | 🟡 medium | Mutated by `get_scc_theme()`. No thread safety. No reset function — leaked across tests. |
| G03 | `output_mode.py` | 39–40 | `console`, `err_console` | Module-level `Console()` instances | 🟡 medium | Created at import time. Any test that imports this module gets shared mutable Console state. Not guarded by ContextVar. |
| G04 | `cli_common.py` | 42–43 | `console`, `err_console` | Module-level `Console()` instances | 🟢 low | Same pattern as output_mode.py. Read-only in practice but shared mutable Rich state. |
| G05 | `cli_helpers.py` | 23–24 | `console`, `stderr_console` | Module-level `Console()` instances | 🟢 low | Same pattern. |
| G06 | `commands/audit.py` | 27 | `console` | Module-level `Console()` | 🟢 low | Same pattern. |
| G07 | `commands/exceptions.py` | 40 | `console` | Module-level `Console()` | 🟢 low | Same pattern. |
| G08 | `commands/reset.py` | 47 | `console` | Module-level `Console()` | 🟢 low | Same pattern. |
| G09 | `deprecation.py` | 20 | `_stderr_console` | Module-level `Console(stderr=True)` | 🟢 low | Same pattern. |
| G10 | `ui/gate.py` | 46 | `_stderr_console` | Module-level `Console(stderr=True)` | 🟢 low | Same pattern. |

### 1b. Module-level mutable dicts used as config/lookup (mutation risk)

| # | File | Line | Name | Severity | Notes |
|---|------|------|------|----------|-------|
| G11 | `config.py` | 46 | `USER_CONFIG_DEFAULTS` | 🟡 medium | Mutable `dict` literal. Read-only in practice (subscript access) but callers could mutate it. Should be `MappingProxyType` or `Final`. |
| G12 | `docker/launch.py` | 37 | `DEFAULT_SAFETY_NET_POLICY` | 🟡 medium | Mutable `dict`. Type annotation says `dict[str, Any]` — no freezing. |
| G13 | `core/exit_codes.py` | 49, 96 | `EXIT_CODE_MAP`, `ERROR_FOOTERS` | 🟢 low | Mutable dicts. Read-only in practice. |
| G14 | `core/git_safety_rules.py` | 153, 207 | `BLOCK_MESSAGES`, `_RULE_NAMES` | 🟢 low | Mutable dicts. Read-only in practice. |
| G15 | `core/safety_engine.py` | 19 | `_MATCHED_RULE_TO_POLICY_KEY` | 🟢 low | Mutable dict. Read-only. |
| G16 | `core/destination_registry.py` | 17 | `PROVIDER_DESTINATION_SETS` | 🟢 low | Mutable dict of DestinationSet values. |
| G17 | `core/network_policy.py` | 9 | `_NETWORK_POLICY_ORDER` | 🟢 low | Mutable dict. |
| G18 | `deps.py` | 37, 81 | `DETECTION_ORDER`, `INSTALL_COMMANDS` | 🟢 low | Mutable list and dict. |
| G19 | `org_templates.py` | 49 | `TEMPLATES` | 🟢 low | Mutable dict of template strings. |
| G20 | `marketplace/constants.py` | 41 | `EXIT_CODES` | 🟢 low | Mutable dict of ints. |
| G21 | `update.py` | 59 | `_PRERELEASE_ORDER` | 🟢 low | Mutable dict. |
| G22 | `ui/help.py` | 43 | `_MODE_NAMES` | 🟢 low | Mutable dict. |

### 1c. Cached singletons with side effects

| # | File | Line | Name | Severity | Notes |
|---|------|------|------|----------|-------|
| G23 | `bootstrap.py` | 74 | `get_default_adapters()` | 🟡 medium | `@lru_cache(maxsize=1)` on a function that probes Docker at import time and returns mutable `DefaultAdapters` dataclass. Cache survives test isolation. Probing side effect fires on first call. |
| G24 | `theme.py` | 87 | `_UNICODE_SUPPORTED` | 🟢 low | `bool` computed at import from `_supports_unicode()`. Immutable after init but freezes terminal detection at import time. |

---

## 2. Subprocess Handling Defects

### 2a. Missing timeout (can hang indefinitely)

| # | File | Line | Call | Severity | Notes |
|---|------|------|------|----------|-------|
| S01 | `config.py` | 360 | `subprocess.run([editor, str(CONFIG_FILE)])` | 🔴 high | Opens user's `$EDITOR` with no timeout and no capture. Hangs if editor blocks. No error handling around it. |
| S02 | `commands/profile.py` | 115 | `subprocess.run(["git", ...], capture_output=True)` | 🟡 medium | Git rev-list with no timeout. Could hang on large repos or network operations. |
| S03 | `commands/profile.py` | 166 | `subprocess.run(cmd, capture_output=True, text=True)` | 🟡 medium | Git diff with no timeout. |
| S04 | `commands/worktree/worktree_commands.py` | 605 | `subprocess.run(argv, cwd=..., env=...)` | 🔴 high | Launches interactive shell. No timeout, no capture, no check. Expected to block, but if shell crashes, returncode is silently discarded. |
| S05 | `deps.py` | 140 | `subprocess.run(cmd, cwd=workspace, capture_output=True, text=True)` | 🟡 medium | Package manager install. No timeout — `npm install` can hang. |
| S06 | `docker/launch.py` | 503 | `subprocess.run(cmd, text=True)` | 🔴 high | Windows-only Docker sandbox exec. No timeout, no capture, no check. |
| S07 | `ui/dashboard/orchestrator.py` | 1051 | `subprocess.run(cmd)` | 🔴 high | Docker `exec -it bash`. No timeout, no capture, no check. |
| S08 | `ui/dashboard/orchestrator.py` | 1162 | `subprocess.run(["git", "worktree", "remove", ...], check=True)` | 🟡 medium | No timeout. Git worktree remove can hang on locked resources. |
| S09 | `ui/dashboard/orchestrator.py` | 831, 846 | `subprocess.run(["git", "init", ...], check=True, ...)` | 🟡 medium | Two git init calls. Both have `check=True`, `capture_output=True`, but no timeout. |
| S10 | `ui/git_interactive.py` | 869 | `subprocess.run(["git", "config", "--global", ...], capture_output=True)` | 🟡 medium | No timeout. No check. Silently ignores failure to set git hooks path. |
| S11 | `marketplace/materialize.py` | 327 | `subprocess.run(["git", "-C", ..., "rev-parse", "HEAD"], ...)` | 🟡 medium | No timeout. Adjacent clone call (line 313) has timeout but this rev-parse does not. |
| S12 | `marketplace/team_fetch.py` | 582 | `subprocess.run(["git", "-C", ..., "rev-parse", "HEAD"], ...)` | 🟡 medium | Same pattern as S11. Clone has timeout; rev-parse does not. |

### 2b. Missing error handling (returncode silently discarded)

| # | File | Line | Call | Severity | Notes |
|---|------|------|------|----------|-------|
| S13 | `docker/core.py` | 314 | `subprocess.Popen(cmd, ...)` | 🟡 medium | `run_detached()` returns Popen but caller never checks if process started. No timeout for Popen creation. |
| S14 | `docker/core.py` | 371, 430, 472, 528 | Multiple `subprocess.run()` | 🟢 low | All have timeout and capture but no `check=True`. Returncode is manually inspected by callers — acceptable pattern. |
| S15 | `auth.py` | 122 | `subprocess.run(["claude", ...], timeout=10, capture_output=True)` | 🟢 low | Has timeout and capture. Checks returncode manually. Acceptable. |

### 2c. No `FileNotFoundError` handling (binary may not exist)

| # | File | Line | Call | Severity | Notes |
|---|------|------|------|----------|-------|
| S16 | `config.py` | 360 | Editor launch | 🟡 medium | No `FileNotFoundError` guard. If `$EDITOR` is not found, unhandled exception propagates. |
| S17 | `deps.py` | 140 | Package manager install | 🟡 medium | No `FileNotFoundError` guard for missing `npm`/`pnpm`/`yarn`/`bun`. |
| S18 | `ui/dashboard/orchestrator.py` | 1051 | Docker exec | 🟡 medium | No `FileNotFoundError` guard for missing `docker` binary. |
| S19 | `ui/git_interactive.py` | 869 | Git config --global | 🟡 medium | No `FileNotFoundError` guard for git binary. |

---

## 3. Silent Exception Swallowing

### 3a. `except Exception: pass` — completely silent, no logging

| # | File | Line | Context | Severity | Notes |
|---|------|------|---------|----------|-------|
| E01 | `application/dashboard.py` | 698 | Loading recent session for "Resume last" item | 🟡 medium | Corrupted session data silently hidden from user. Dashboard shows no "Resume" option with no explanation. |
| E02 | `application/dashboard.py` | 749 | Loading personal profile info | 🟡 medium | Profile display silently falls back to "none". |
| E03 | `application/dashboard.py` | 800 | Container count for dashboard status | 🟡 medium | Docker errors silently swallowed. Container section disappears with no feedback. |
| E04 | `update.py` | 247 | Detecting installation method (editable/pipx/etc.) | 🟢 low | Non-critical metadata. Silent fallback is acceptable but should log at DEBUG. |
| E05 | `core/personal_profiles.py` | 830 | Checking sandbox import candidates | 🟡 medium | Docker/profile errors silently suppressed. `import_count` defaults to 0 with no indication of failure. |
| E06 | `docker/credentials.py` | 536 | Debug log write in `_debug()` helper | 🟢 low | Debug logging itself fails silently — acceptable, avoids infinite recursion. |
| E07 | `docker/credentials.py` | 632 | Credential migration retry | 🟡 medium | Credential operation failure silently swallowed inside retry loop. Could leave credentials in inconsistent state. |
| E08 | `application/support_bundle.py` | 267, 276, 284 | Three collection steps in support bundle | 🟢 low | Support bundle is best-effort — silent skip is intentional but loses diagnostic info. |
| E09 | `application/worktree/use_cases.py` | 886, 890 | Worktree cleanup operations | 🟡 medium | Git cleanup silently fails. Stale worktree entries may accumulate. |
| E10 | `maintenance/health_checks.py` | 167 | Stale lock cleanup | 🟡 medium | Failed lock cleanup silently ignored. Stale locks persist. |
| E11 | `maintenance/cache_cleanup.py` | 174 | Single cache directory cleanup | 🟢 low | Per-item skip in cleanup loop. Acceptable but unlogged. |
| E12 | `doctor/checks/cache.py` | 214 | Cache directory stat | 🟢 low | Doctor check silently skips unreadable cache. |
| E13 | `utils/ttl.py` | 58 | TTL cache file read | 🟡 medium | Cache corruption silently swallowed. Stale data may be served instead of cache miss. |

### 3b. `except Exception:` with logging but overly broad catch

| # | File | Line | Context | Severity | Notes |
|---|------|------|---------|----------|-------|
| E14 | `core/safety_policy_loader.py` | 65 | Policy file parse | 🟡 medium | Returns default "block" policy on any error, including `PermissionError`. Correct fail-safe behavior but hides root cause. |
| E15 | `commands/launch/flow.py` | 874 | Docker sandbox preparation | 🟡 medium | Catches all exceptions during sandbox prep, assigns generic error string. |
| E16 | `application/settings/use_cases.py` | 379, 390, 403 | Three settings info loaders | 🟡 medium | All catch `Exception` and return fallback values. Masks real errors (permission, disk full). |
| E17 | `application/dashboard.py` | 856, 922, 993 | Three dashboard data loaders | 🟡 medium | Return empty/fallback data on any exception. |
| E18 | `contexts.py` | 205 | Context manager cleanup | 🟡 medium | Broad catch during cleanup could mask resource leaks. |
| E19 | `ui/picker.py` | 475 | Session picker fallback | 🟢 low | Returns empty list on any error — acceptable for UI fallback. |
| E20 | `utils/fixit.py` | 27 | Terminal width detection | 🟢 low | Returns 80 on any error. Acceptable. |

---

## 4. Summary Statistics

| Category | 🔴 High | 🟡 Medium | 🟢 Low | Total |
|----------|---------|-----------|--------|-------|
| Global mutable state | 0 | 5 | 19 | 24 |
| Subprocess: missing timeout | 4 | 8 | 0 | 12 |
| Subprocess: missing error handling | 0 | 1 | 2 | 3 |
| Subprocess: missing FileNotFoundError guard | 0 | 4 | 0 | 4 |
| Silent swallow (pass) | 0 | 7 | 6 | 13 |
| Silent swallow (broad catch) | 0 | 6 | 1 | 7 |
| **Total** | **4** | **31** | **28** | **63** |

## 5. Priority Repair Queue

### Immediate (block S02 surgery if not addressed)

1. **S01** — `config.py:360` editor launch: add timeout, `FileNotFoundError` guard, returncode check.
2. **S06** — `docker/launch.py:503` Windows sandbox exec: add timeout and returncode check.
3. **S07** — `orchestrator.py:1051` Docker exec: add timeout and `FileNotFoundError` guard.
4. **G01** — `console.py` global Console singletons: convert to ContextVar or inject.
5. **G23** — `bootstrap.py` `@lru_cache` on `get_default_adapters()`: Docker probe side effect fires once and caches forever; blocks test isolation.

### Next batch (address during S02 refactors)

6. **G02** — `theme.py` singleton: add reset function for test isolation.
7. **G03** — `output_mode.py` module-level Consoles: align with `console.py` lazy pattern.
8. **G11/G12** — Mutable config dicts: freeze with `MappingProxyType` or `Final`.
9. **E01–E03** — Dashboard silent swallows: add structured logging.
10. **E07** — `credentials.py:632` credential migration silent swallow: log the failure.
11. **E13** — `ttl.py:58` cache corruption swallow: treat as cache miss, not stale hit.
12. **S11/S12** — `materialize.py`/`team_fetch.py` git rev-parse without timeout.
