"""Tests for the provider destination registry — resolution, errors, and rule generation."""

from __future__ import annotations

import pytest

from scc_cli.core.contracts import DestinationSet, EgressRule
from scc_cli.core.destination_registry import (
    PROVIDER_DESTINATION_SETS,
    destination_sets_to_allow_rules,
    resolve_destination_sets,
)

# ---------------------------------------------------------------------------
# Registry contents
# ---------------------------------------------------------------------------


class TestRegistryContents:
    """Verify the canonical registry has the expected provider entries."""

    def test_anthropic_core_present(self) -> None:
        ds = PROVIDER_DESTINATION_SETS["anthropic-core"]
        assert ds.name == "anthropic-core"
        assert "api.anthropic.com" in ds.destinations
        assert ds.required is True

    def test_openai_core_present(self) -> None:
        ds = PROVIDER_DESTINATION_SETS["openai-core"]
        assert ds.name == "openai-core"
        assert "api.openai.com" in ds.destinations
        assert ds.required is True

    def test_all_entries_are_destination_sets(self) -> None:
        for key, ds in PROVIDER_DESTINATION_SETS.items():
            assert isinstance(ds, DestinationSet), f"{key} is not a DestinationSet"
            assert ds.name == key, f"name mismatch: {ds.name!r} != {key!r}"


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


class TestResolveDestinationSets:
    """Test resolve_destination_sets with valid and invalid inputs."""

    def test_resolve_anthropic_core(self) -> None:
        result = resolve_destination_sets(("anthropic-core",))
        assert len(result) == 1
        assert result[0].name == "anthropic-core"

    def test_resolve_openai_core(self) -> None:
        result = resolve_destination_sets(("openai-core",))
        assert len(result) == 1
        assert result[0].name == "openai-core"

    def test_resolve_multiple_sets(self) -> None:
        result = resolve_destination_sets(("anthropic-core", "openai-core"))
        assert len(result) == 2
        assert result[0].name == "anthropic-core"
        assert result[1].name == "openai-core"

    def test_resolve_preserves_order(self) -> None:
        result = resolve_destination_sets(("openai-core", "anthropic-core"))
        assert result[0].name == "openai-core"
        assert result[1].name == "anthropic-core"

    def test_empty_input_returns_empty_tuple(self) -> None:
        result = resolve_destination_sets(())
        assert result == ()

    def test_unknown_name_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown destination set 'nonexistent'"):
            resolve_destination_sets(("nonexistent",))

    def test_unknown_among_valid_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown destination set 'bad-name'"):
            resolve_destination_sets(("anthropic-core", "bad-name"))


# ---------------------------------------------------------------------------
# Rule generation
# ---------------------------------------------------------------------------


class TestDestinationSetsToAllowRules:
    """Test allow-rule generation from resolved destination sets."""

    def test_single_set_single_host(self) -> None:
        sets = (
            DestinationSet(
                name="test-set",
                destinations=("example.com",),
                required=True,
                description="test",
            ),
        )
        rules = destination_sets_to_allow_rules(sets)
        assert len(rules) == 1
        assert rules[0] == EgressRule(
            target="example.com",
            allow=True,
            reason="provider-core: test-set",
        )

    def test_single_set_multiple_hosts(self) -> None:
        sets = (
            DestinationSet(
                name="multi",
                destinations=("a.example.com", "b.example.com"),
                required=False,
                description="multi-host test",
            ),
        )
        rules = destination_sets_to_allow_rules(sets)
        assert len(rules) == 2
        assert rules[0].target == "a.example.com"
        assert rules[1].target == "b.example.com"
        assert all(r.allow is True for r in rules)
        assert all(r.reason == "provider-core: multi" for r in rules)

    def test_multiple_sets_produce_combined_rules(self) -> None:
        anthropic = PROVIDER_DESTINATION_SETS["anthropic-core"]
        openai = PROVIDER_DESTINATION_SETS["openai-core"]
        rules = destination_sets_to_allow_rules((anthropic, openai))
        targets = [r.target for r in rules]
        assert "api.anthropic.com" in targets
        assert "api.openai.com" in targets
        assert all(r.allow is True for r in rules)

    def test_rule_targets_match_set_hosts(self) -> None:
        sets = resolve_destination_sets(("anthropic-core",))
        rules = destination_sets_to_allow_rules(sets)
        rule_targets = {r.target for r in rules}
        set_hosts = set(sets[0].destinations)
        assert rule_targets == set_hosts

    def test_empty_sets_returns_empty_rules(self) -> None:
        rules = destination_sets_to_allow_rules(())
        assert rules == ()

    def test_all_rules_are_egress_rule_instances(self) -> None:
        sets = resolve_destination_sets(("anthropic-core", "openai-core"))
        rules = destination_sets_to_allow_rules(sets)
        for rule in rules:
            assert isinstance(rule, EgressRule)

    def test_reason_format_contains_set_name(self) -> None:
        sets = resolve_destination_sets(("openai-core",))
        rules = destination_sets_to_allow_rules(sets)
        for rule in rules:
            assert "openai-core" in rule.reason
            assert rule.reason.startswith("provider-core: ")
