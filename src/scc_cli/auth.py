"""
Resolve authentication from environment variables and commands.

Consolidate auth logic from remote.py and claude_adapter.py.
Use safe command execution (no shell=True).

Trust Model:
- User config auth: Trusted (local file, user controls)
- Remote org config auth: Less trusted (org admin controls)
  - command: requires explicit opt-in for remote sources

Security Features:
- shell=False to prevent shell injection
- Platform-aware shlex.split() for command parsing
- Binary validation with shutil.which()
- Sanitized error messages (no secrets in errors)
- Reduced timeout (10s instead of 30s)
"""

import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class AuthResult:
    """Result of resolving auth spec.

    Attributes:
        token: The resolved authentication token
        source: Where the token came from ('env' or 'command')
        env_name: The environment variable name (if source='env')
    """

    token: str
    source: str  # 'env' or 'command'
    env_name: str | None = None


def resolve_auth(
    auth_spec: str | None,
    allow_command: bool = True,
) -> AuthResult | None:
    """Resolve auth spec to token.

    Supports:
    - env:VAR_NAME - read from environment variable (always allowed)
    - command:CMD - execute command (requires allow_command=True)
    - None or empty - no auth needed

    Args:
        auth_spec: Auth specification string
        allow_command: Whether to allow command: specs (default True for
            user config, should be False for remote org config unless
            explicitly opted in)

    Returns:
        AuthResult with token and source, or None if no auth

    Raises:
        ValueError: Invalid auth spec format or command not allowed
        RuntimeError: Auth command failed
    """
    if not auth_spec or not auth_spec.strip():
        return None

    auth_spec = auth_spec.strip()

    if auth_spec.startswith("env:"):
        return _resolve_env_auth(auth_spec)

    if auth_spec.startswith("command:"):
        if not allow_command:
            raise ValueError(
                "command: auth not allowed from remote config. "
                "Use --allow-remote-commands or SCC_ALLOW_REMOTE_COMMANDS=1"
            )
        return _execute_auth_command(auth_spec[8:].strip())

    raise ValueError(f"Invalid auth spec format: {auth_spec}")


def _resolve_env_auth(auth_spec: str) -> AuthResult | None:
    """Resolve env:VAR_NAME auth spec."""
    var_name = auth_spec[4:].strip()
    if not var_name:
        return None

    token = os.environ.get(var_name)
    if token and token.strip():
        return AuthResult(token=token.strip(), source="env", env_name=var_name)
    return None


def _execute_auth_command(cmd: str) -> AuthResult | None:
    """Execute auth command safely (no shell injection).

    SECURITY: Uses shell=False and shlex.split() to prevent shell injection.
    """
    if not cmd:
        return None

    try:
        # Platform-aware splitting (Windows uses different escaping)
        use_posix = sys.platform != "win32"
        args = shlex.split(cmd, posix=use_posix)
    except ValueError:
        raise RuntimeError("Invalid auth command syntax") from None

    if not args:
        return None

    # Validate executable exists (prevents PATH hijacking, clearer errors)
    executable = shutil.which(args[0])
    if not executable:
        raise RuntimeError(f"Auth command executable not found: {args[0]}")

    try:
        result = subprocess.run(
            [executable] + args[1:],  # Use resolved absolute path
            shell=False,  # CRITICAL: No shell interpretation
            capture_output=True,
            text=True,
            timeout=10,  # Reduced from 30s
        )
        if result.returncode == 0 and result.stdout.strip():
            return AuthResult(token=result.stdout.strip(), source="command")
        return None
    except subprocess.TimeoutExpired:
        raise RuntimeError("Auth command timed out after 10s")
    except OSError:
        # Don't leak command in error (might contain secrets)
        raise RuntimeError("Auth command failed")


def is_remote_command_allowed() -> bool:
    """Check if command: auth is allowed from remote org config.

    Returns True if SCC_ALLOW_REMOTE_COMMANDS is set to 1, true, or yes.
    """
    value = os.environ.get("SCC_ALLOW_REMOTE_COMMANDS", "").lower()
    return value in ("1", "true", "yes")
