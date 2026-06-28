"""Project-level policy constraints for effective config."""

from scc_cli.application.compute_effective_config import compute_effective_config


def _org_config_with_default_policy(policy: str) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "organization": {
            "name": "Example Municipality",
            "id": "example",
        },
        "defaults": {
            "network_policy": policy,
        },
        "delegation": {
            "projects": {
                "inherit_team_delegation": True,
            },
        },
        "profiles": {
            "platform": {
                "delegation": {
                    "allow_project_overrides": True,
                },
            },
        },
    }


def _org_config_with_default_and_team_policy(
    default_policy: str, team_policy: str
) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "organization": {
            "name": "Example Municipality",
            "id": "example",
        },
        "defaults": {
            "network_policy": default_policy,
        },
        "profiles": {
            "platform": {
                "network_policy": team_policy,
            },
        },
    }


def _org_config_with_team_policy(policy: str) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "organization": {
            "name": "Example Municipality",
            "id": "example",
        },
        "profiles": {
            "platform": {
                "network_policy": policy,
            },
        },
    }


def test_team_context_cannot_widen_network_policy() -> None:
    result = compute_effective_config(
        org_config=_org_config_with_default_and_team_policy("locked-down-web", "open"),
        team_name="platform",
    )

    assert result.network_policy == "locked-down-web"
    assert not any(
        decision.field == "network_policy" and decision.source == "team.platform"
        for decision in result.decisions
    )
    assert result.ignored_policy_changes
    ignored = result.ignored_policy_changes[0]
    assert ignored.field == "network_policy"
    assert ignored.source == "team.platform"
    assert ignored.requested_value == "open"
    assert ignored.effective_value == "locked-down-web"
    assert ignored.reason == "Team network_policy cannot be less restrictive than inherited policy"


def test_team_context_ignores_unknown_network_policy_value() -> None:
    result = compute_effective_config(
        org_config=_org_config_with_team_policy("isolated"),
        team_name="platform",
    )

    assert result.network_policy is None
    assert result.ignored_policy_changes
    ignored = result.ignored_policy_changes[0]
    assert ignored.source == "team.platform"
    assert ignored.requested_value == "isolated"
    assert ignored.effective_value is None
    assert ignored.reason == "Unknown team network_policy value"


def test_project_context_cannot_widen_network_policy() -> None:
    result = compute_effective_config(
        org_config=_org_config_with_default_policy("locked-down-web"),
        team_name="platform",
        project_config={"network_policy": "open"},
    )

    assert result.network_policy == "locked-down-web"
    assert not any(
        decision.field == "network_policy" and decision.source == "project"
        for decision in result.decisions
    )
    assert result.ignored_policy_changes
    ignored = result.ignored_policy_changes[0]
    assert ignored.field == "network_policy"
    assert ignored.source == "project"
    assert ignored.requested_value == "open"
    assert ignored.effective_value == "locked-down-web"


def test_project_context_cannot_widen_to_web_egress_enforced() -> None:
    result = compute_effective_config(
        org_config=_org_config_with_default_policy("locked-down-web"),
        team_name="platform",
        project_config={"network_policy": "web-egress-enforced"},
    )

    assert result.network_policy == "locked-down-web"
    assert not any(
        decision.field == "network_policy" and decision.source == "project"
        for decision in result.decisions
    )
    assert result.ignored_policy_changes[0].requested_value == "web-egress-enforced"
    assert result.ignored_policy_changes[0].effective_value == "locked-down-web"


def test_project_context_ignores_unknown_network_policy_value() -> None:
    result = compute_effective_config(
        org_config=_org_config_with_default_policy("locked-down-web"),
        team_name="platform",
        project_config={"network_policy": "isolated"},
    )

    assert result.network_policy == "locked-down-web"
    ignored = result.ignored_policy_changes[0]
    assert ignored.field == "network_policy"
    assert ignored.requested_value == "isolated"
    assert ignored.effective_value == "locked-down-web"
    assert ignored.reason == "Unknown project network_policy value"


def test_project_context_can_narrow_network_policy() -> None:
    result = compute_effective_config(
        org_config=_org_config_with_default_policy("open"),
        team_name="platform",
        project_config={"network_policy": "locked-down-web"},
    )

    assert result.network_policy == "locked-down-web"
    assert any(
        decision.field == "network_policy" and decision.source == "project"
        for decision in result.decisions
    )


def test_project_context_can_narrow_to_web_egress_enforced() -> None:
    result = compute_effective_config(
        org_config=_org_config_with_default_policy("open"),
        team_name="platform",
        project_config={"network_policy": "web-egress-enforced"},
    )

    assert result.network_policy == "web-egress-enforced"
    assert any(
        decision.field == "network_policy" and decision.source == "project"
        for decision in result.decisions
    )
