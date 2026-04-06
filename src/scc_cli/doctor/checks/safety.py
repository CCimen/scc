"""Safety-policy health check for the doctor module.

Verifies that the safety-net policy section of the org config is present,
well-formed, and produces a valid ``SafetyPolicy``.
"""

from __future__ import annotations

from scc_cli import config as _config_module
from scc_cli.core.enums import SeverityLevel
from scc_cli.core.safety_policy_loader import VALID_SAFETY_NET_ACTIONS, load_safety_policy

from ..types import CheckResult


def _load_raw_org_config() -> dict[str, object] | None:
    """Indirection for testability — returns raw cached org config."""
    return _config_module.load_cached_org_config()


def check_safety_policy() -> CheckResult:
    """Probe org config availability and safety-policy validity.

    Uses ``config.load_cached_org_config()`` for the raw org config dict
    (same access pattern as the other organisation checks) and feeds it
    through ``load_safety_policy()`` for typed validation.

    Returns
    -------
    CheckResult
        PASS  — valid ``security.safety_net`` section with a recognised action.
        WARNING — no org config, or org config without ``safety_net`` section.
        ERROR — invalid action value, or unexpected failure during probing.
    """
    try:
        raw_org = _load_raw_org_config()

        if raw_org is None:
            return CheckResult(
                name="Safety Policy",
                passed=True,
                message="No org config found, using default block policy",
                severity=SeverityLevel.WARNING,
            )

        # Check structural presence before running the full loader.
        security = raw_org.get("security") if isinstance(raw_org, dict) else None
        if not isinstance(security, dict) or "safety_net" not in security:
            return CheckResult(
                name="Safety Policy",
                passed=True,
                message="No safety_net section in org config, using default block policy",
                severity=SeverityLevel.WARNING,
            )

        safety_net = security.get("safety_net")
        if isinstance(safety_net, dict):
            raw_action = safety_net.get("action")
            if isinstance(raw_action, str) and raw_action not in VALID_SAFETY_NET_ACTIONS:
                valid_str = ", ".join(sorted(VALID_SAFETY_NET_ACTIONS))
                return CheckResult(
                    name="Safety Policy",
                    passed=False,
                    message=f"Invalid safety_net action '{raw_action}' — falling back to 'block'",
                    fix_hint=f"Set security.safety_net.action to one of: {valid_str}",
                    severity=SeverityLevel.ERROR,
                )

        # Full typed load — should succeed given structural checks above.
        policy = load_safety_policy(raw_org)
        return CheckResult(
            name="Safety Policy",
            passed=True,
            message=f"Effective action: {policy.action}",
        )

    except Exception as exc:
        return CheckResult(
            name="Safety Policy",
            passed=False,
            message=f"Unexpected error probing safety policy: {exc}",
            severity=SeverityLevel.ERROR,
        )
