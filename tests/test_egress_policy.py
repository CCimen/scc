"""Tests for egress plan builder and Squid ACL compiler.

Covers all three NetworkPolicy modes, default deny rules, ACL compilation,
ordering invariants, and boundary conditions.
"""

from __future__ import annotations

from scc_cli.core.contracts import (
    DestinationSet,
    EgressRule,
    NetworkPolicyPlan,
)
from scc_cli.core.egress_policy import build_egress_plan, compile_squid_acl
from scc_cli.core.enums import NetworkPolicy

# ═══════════════════════════════════════════════════════════════════════════════
# build_egress_plan() — mode behavior
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildEgressPlanModes:
    """Plan builder produces correct plans for each NetworkPolicy mode."""

    def test_open_mode_produces_no_rules(self) -> None:
        plan = build_egress_plan(NetworkPolicy.OPEN)

        assert plan.mode is NetworkPolicy.OPEN
        assert plan.egress_rules == ()
        assert plan.enforced_by_runtime is False

    def test_enforced_mode_has_default_deny_rules(self) -> None:
        plan = build_egress_plan(NetworkPolicy.WEB_EGRESS_ENFORCED)

        assert plan.mode is NetworkPolicy.WEB_EGRESS_ENFORCED
        assert plan.enforced_by_runtime is True

        deny_targets = {r.target for r in plan.egress_rules if not r.allow}
        assert "127.0.0.0/8" in deny_targets, "loopback missing"
        assert "10.0.0.0/8" in deny_targets, "private /8 missing"
        assert "172.16.0.0/12" in deny_targets, "private /12 missing"
        assert "192.168.0.0/16" in deny_targets, "private /16 missing"
        assert "169.254.0.0/16" in deny_targets, "link-local missing"
        assert "169.254.169.254" in deny_targets, "metadata endpoint missing"

    def test_locked_down_mode_has_no_rules(self) -> None:
        plan = build_egress_plan(NetworkPolicy.LOCKED_DOWN_WEB)

        assert plan.mode is NetworkPolicy.LOCKED_DOWN_WEB
        assert plan.enforced_by_runtime is True
        assert plan.egress_rules == ()
        assert any("--network=none" in n for n in plan.notes)


# ═══════════════════════════════════════════════════════════════════════════════
# build_egress_plan() — rule composition
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildEgressPlanRules:
    """Plan builder correctly threads allow rules and destination sets."""

    def test_enforced_mode_with_allow_rules(self) -> None:
        custom = (
            EgressRule(target=".anthropic.com", allow=True, reason="provider API"),
            EgressRule(target=".github.com", allow=True, reason="code host"),
        )
        plan = build_egress_plan(
            NetworkPolicy.WEB_EGRESS_ENFORCED, egress_rules=custom
        )

        # Custom allow rules appear after the default deny set.
        allow_targets = [r.target for r in plan.egress_rules if r.allow]
        assert ".anthropic.com" in allow_targets
        assert ".github.com" in allow_targets

        # Deny rules should still be first.
        first_allow_idx = next(
            i for i, r in enumerate(plan.egress_rules) if r.allow
        )
        for r in plan.egress_rules[:first_allow_idx]:
            assert r.allow is False

    def test_enforced_mode_with_destination_sets(self) -> None:
        ds = (
            DestinationSet(
                name="claude-api",
                destinations=("api.anthropic.com", "sentry.io"),
                required=True,
            ),
        )
        plan = build_egress_plan(
            NetworkPolicy.WEB_EGRESS_ENFORCED, destination_sets=ds
        )

        assert plan.destination_sets == ds
        assert plan.destination_sets[0].name == "claude-api"


# ═══════════════════════════════════════════════════════════════════════════════
# build_egress_plan() — boundary / malformed inputs
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildEgressPlanEdgeCases:
    """Edge cases and malformed inputs for the plan builder."""

    def test_empty_destination_set_tuple(self) -> None:
        plan = build_egress_plan(NetworkPolicy.WEB_EGRESS_ENFORCED, destination_sets=())
        assert plan.destination_sets == ()

    def test_egress_rule_with_empty_target(self) -> None:
        custom = (EgressRule(target="", allow=True, reason="empty target"),)
        plan = build_egress_plan(
            NetworkPolicy.WEB_EGRESS_ENFORCED, egress_rules=custom
        )
        # Empty target is accepted; compile_squid_acl will treat it as dstdomain.
        allow_targets = [r.target for r in plan.egress_rules if r.allow]
        assert "" in allow_targets

    def test_enforced_mode_with_zero_allow_rules(self) -> None:
        plan = build_egress_plan(NetworkPolicy.WEB_EGRESS_ENFORCED)
        allow_rules = [r for r in plan.egress_rules if r.allow]
        assert allow_rules == []
        # Should still have deny rules.
        deny_rules = [r for r in plan.egress_rules if not r.allow]
        assert len(deny_rules) >= 6


# ═══════════════════════════════════════════════════════════════════════════════
# compile_squid_acl() — ACL output
# ═══════════════════════════════════════════════════════════════════════════════


class TestCompileSquidAcl:
    """Squid ACL compiler produces valid, correctly-ordered output."""

    def test_compile_acl_deny_private_cidrs(self) -> None:
        plan = build_egress_plan(NetworkPolicy.WEB_EGRESS_ENFORCED)
        acl = compile_squid_acl(plan)

        assert "dst 10.0.0.0/8" in acl
        assert "dst 172.16.0.0/12" in acl
        assert "dst 192.168.0.0/16" in acl

    def test_compile_acl_deny_metadata(self) -> None:
        plan = build_egress_plan(NetworkPolicy.WEB_EGRESS_ENFORCED)
        acl = compile_squid_acl(plan)

        assert "dst 169.254.169.254" in acl

    def test_compile_acl_allow_specific_hosts(self) -> None:
        custom = (
            EgressRule(target=".anthropic.com", allow=True, reason="provider API"),
        )
        plan = build_egress_plan(
            NetworkPolicy.WEB_EGRESS_ENFORCED, egress_rules=custom
        )
        acl = compile_squid_acl(plan)

        assert "dstdomain .anthropic.com" in acl

    def test_compile_acl_deny_before_allow_ordering(self) -> None:
        custom = (
            EgressRule(target=".anthropic.com", allow=True, reason="provider API"),
        )
        plan = build_egress_plan(
            NetworkPolicy.WEB_EGRESS_ENFORCED, egress_rules=custom
        )
        acl = compile_squid_acl(plan)

        lines = acl.strip().splitlines()
        access_lines = [
            line for line in lines if line.startswith("http_access")
        ]

        # Find last deny and first allow in access lines (excluding terminal).
        deny_indices = [
            idx for idx, line in enumerate(access_lines)
            if "deny" in line and line != "http_access deny all"
        ]
        allow_indices = [
            idx for idx, line in enumerate(access_lines) if "allow" in line
        ]

        if deny_indices and allow_indices:
            assert max(deny_indices) < min(allow_indices), (
                "all deny rules must precede allow rules"
            )

    def test_compile_acl_ends_with_deny_all(self) -> None:
        plan = build_egress_plan(NetworkPolicy.WEB_EGRESS_ENFORCED)
        acl = compile_squid_acl(plan)

        non_empty = [line for line in acl.strip().splitlines() if line.strip()]
        assert non_empty[-1] == "http_access deny all"

    def test_compile_acl_open_mode_permits_all(self) -> None:
        plan = build_egress_plan(NetworkPolicy.OPEN)
        acl = compile_squid_acl(plan)

        assert acl.strip() == "http_access allow all"

    def test_compile_acl_locked_down_produces_deny_all(self) -> None:
        plan = build_egress_plan(NetworkPolicy.LOCKED_DOWN_WEB)
        acl = compile_squid_acl(plan)

        assert acl.strip() == "http_access deny all"

    def test_compile_acl_loopback_denied(self) -> None:
        plan = build_egress_plan(NetworkPolicy.WEB_EGRESS_ENFORCED)
        acl = compile_squid_acl(plan)

        assert "dst 127.0.0.0/8" in acl

    def test_compile_acl_link_local_denied(self) -> None:
        plan = build_egress_plan(NetworkPolicy.WEB_EGRESS_ENFORCED)
        acl = compile_squid_acl(plan)

        assert "dst 169.254.0.0/16" in acl


# ═══════════════════════════════════════════════════════════════════════════════
# compile_squid_acl() — boundary conditions
# ═══════════════════════════════════════════════════════════════════════════════


class TestCompileSquidAclEdgeCases:
    """Edge cases for the ACL compiler: open mode passthrough, etc."""

    def test_open_mode_plan_through_compiler(self) -> None:
        """OPEN plan passed through compile_squid_acl yields allow all."""
        plan = NetworkPolicyPlan(
            mode=NetworkPolicy.OPEN,
            enforced_by_runtime=False,
        )
        acl = compile_squid_acl(plan)
        assert acl.strip() == "http_access allow all"

    def test_enforced_plan_with_only_deny_rules(self) -> None:
        """Enforced plan with zero allow rules — no allow lines before deny all."""
        plan = build_egress_plan(NetworkPolicy.WEB_EGRESS_ENFORCED)
        acl = compile_squid_acl(plan)

        access_lines = [
            line for line in acl.strip().splitlines()
            if line.startswith("http_access")
        ]
        allow_lines = [line for line in access_lines if "allow" in line]
        assert allow_lines == [], "no allow lines expected with zero allow rules"
