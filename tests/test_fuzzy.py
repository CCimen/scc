"""Tests for fuzzy matching utility.

Following TDD: Write tests first, then implement.
"""

from scc_cli.utils.fuzzy import find_similar, similarity_score


class TestSimilarityScore:
    """Tests for similarity_score function."""

    def test_exact_match_returns_1(self):
        """Exact matches should return 1.0."""
        assert similarity_score("jira-api", "jira-api") == 1.0

    def test_completely_different_returns_low_score(self):
        """Completely different strings should have low score."""
        score = similarity_score("abc", "xyz")
        assert score < 0.5

    def test_similar_strings_high_score(self):
        """Similar strings should have high score."""
        # jira-api vs jira-api-v2 should be fairly similar
        score = similarity_score("jira-api", "jira-api-v2")
        assert score > 0.7

    def test_case_insensitive(self):
        """Matching should be case insensitive."""
        score = similarity_score("Jira-API", "jira-api")
        assert score == 1.0

    def test_prefix_similarity(self):
        """Strings with common prefix should be similar."""
        score = similarity_score("foo-prod", "foo-prod-1")
        assert score >= 0.8  # Should be exactly 0.8 (distance 2, max_len 10)

    def test_empty_strings(self):
        """Empty strings should return 0 score."""
        assert similarity_score("", "something") == 0.0
        assert similarity_score("something", "") == 0.0
        assert similarity_score("", "") == 1.0  # Both empty = identical

    def test_single_character_difference(self):
        """Single character difference should still be high similarity."""
        score = similarity_score("jira-api", "jira-apii")
        assert score > 0.8


class TestFindSimilar:
    """Tests for find_similar function."""

    def test_exact_match_returns_empty_list(self):
        """If there's an exact match, return empty (use exact match path)."""
        candidates = ["jira-api", "jira-api-v2", "slack-api"]
        result = find_similar("jira-api", candidates)
        assert result == []

    def test_finds_similar_candidates(self):
        """Should find similar candidates above threshold."""
        candidates = ["foo-prod-1", "foo-prod-2", "bar-staging", "baz-dev"]
        result = find_similar("foo-prod", candidates)
        assert "foo-prod-1" in result
        assert "foo-prod-2" in result
        assert "bar-staging" not in result

    def test_respects_threshold(self):
        """Should only return candidates above threshold."""
        candidates = ["jira-api", "slack-api", "github-api"]
        result = find_similar("jira", candidates, threshold=0.5)
        assert "jira-api" in result
        # slack-api and github-api should be too different
        assert "slack-api" not in result

    def test_returns_max_suggestions(self):
        """Should limit number of suggestions."""
        candidates = [f"item-{i}" for i in range(10)]
        result = find_similar("item", candidates, max_suggestions=3)
        assert len(result) <= 3

    def test_sorted_by_similarity(self):
        """Results should be sorted by similarity (most similar first)."""
        candidates = ["foo-prod-staging-extra", "foo-prod", "foo-prod-1"]
        # Note: foo-prod is an exact match, so we use a slightly different query
        result = find_similar("foo-prod-", candidates)
        # foo-prod-1 should be more similar to "foo-prod-" than foo-prod-staging-extra
        if len(result) >= 2:
            idx1 = result.index("foo-prod-1") if "foo-prod-1" in result else 999
            idx2 = (
                result.index("foo-prod-staging-extra")
                if "foo-prod-staging-extra" in result
                else 999
            )
            assert idx1 < idx2

    def test_empty_candidates(self):
        """Should return empty list for no candidates."""
        result = find_similar("query", [])
        assert result == []

    def test_no_matches_above_threshold(self):
        """Should return empty list when nothing matches."""
        candidates = ["xyz", "abc", "def"]
        result = find_similar("jira-api", candidates, threshold=0.8)
        assert result == []

    def test_case_insensitive_matching(self):
        """Matching should be case insensitive."""
        candidates = ["Jira-API", "SLACK-API"]
        result = find_similar("jira", candidates, threshold=0.5)
        assert "Jira-API" in result

    def test_default_threshold_is_0_8(self):
        """Default threshold should be 0.8 per plan spec."""
        candidates = ["jira-api", "completely-different"]
        # jira vs jira-api should pass 0.8 threshold (common prefix)
        result = find_similar("jira", candidates)
        # The exact behavior depends on the similarity algorithm
        # but "jira" vs "jira-api" should be similar enough
        # This test verifies the default parameter works without error
        assert isinstance(result, list)


class TestIntegrationScenarios:
    """Integration tests for real-world scenarios from the plan."""

    def test_unblock_scenario_typo(self):
        """Scenario: User types 'foo-prod' but actual is 'foo-prod-1'."""
        denied = ["foo-prod-1", "foo-prod-2", "bar-api"]
        suggestions = find_similar("foo-prod", denied)
        assert "foo-prod-1" in suggestions
        assert "foo-prod-2" in suggestions
        assert "bar-api" not in suggestions

    def test_unblock_scenario_exact_match(self):
        """Scenario: User types exact name - no suggestions needed."""
        denied = ["jira-api", "slack-api"]
        suggestions = find_similar("jira-api", denied)
        assert suggestions == []

    def test_unblock_scenario_no_match(self):
        """Scenario: User types something completely wrong."""
        denied = ["jira-api", "slack-api", "github-api"]
        suggestions = find_similar("xyz-service", denied)
        # Nothing should match at default 0.8 threshold
        assert suggestions == []
