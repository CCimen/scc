"""Provide fuzzy matching utilities for DX improvements.

Offer fuzzy string matching to suggest corrections when users
make typos or partial matches in CLI commands.

Use Levenshtein-based similarity for >80% threshold matching.
"""

from __future__ import annotations


def similarity_score(s1: str, s2: str) -> float:
    """Calculate similarity score between two strings.

    Uses normalized Levenshtein distance for similarity scoring.
    Returns value between 0.0 (completely different) and 1.0 (identical).

    The comparison is case-insensitive.

    Args:
        s1: First string
        s2: Second string

    Returns:
        Similarity score from 0.0 to 1.0
    """
    # Handle edge cases
    if not s1 and not s2:
        return 1.0  # Both empty = identical
    if not s1 or not s2:
        return 0.0  # One empty = no similarity

    # Case-insensitive comparison
    s1_lower = s1.lower()
    s2_lower = s2.lower()

    # Calculate Levenshtein distance
    distance = _levenshtein_distance(s1_lower, s2_lower)

    # Normalize by max length to get similarity
    max_len = max(len(s1_lower), len(s2_lower))
    return 1.0 - (distance / max_len)


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate Levenshtein (edit) distance between two strings.

    Uses dynamic programming approach for efficiency.

    Args:
        s1: First string
        s2: Second string

    Returns:
        Minimum number of single-character edits needed
    """
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    # Use only two rows for space efficiency
    previous_row = list(range(len(s2) + 1))
    current_row = [0] * (len(s2) + 1)

    for i, c1 in enumerate(s1):
        current_row[0] = i + 1
        for j, c2 in enumerate(s2):
            # Cost is 0 if characters match, 1 otherwise
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (0 if c1 == c2 else 1)
            current_row[j + 1] = min(insertions, deletions, substitutions)

        previous_row, current_row = current_row, previous_row

    return previous_row[len(s2)]


def find_similar(
    query: str,
    candidates: list[str],
    threshold: float = 0.8,
    max_suggestions: int = 5,
) -> list[str]:
    """Find similar candidates to a query string.

    Returns candidates that are similar to the query (above threshold),
    sorted by similarity (most similar first).

    If the query exactly matches a candidate, returns empty list
    (caller should use the exact match, not suggestions).

    Args:
        query: The string to match against
        candidates: List of possible matches
        threshold: Minimum similarity score (0.0-1.0), default 0.8
        max_suggestions: Maximum number of suggestions to return

    Returns:
        List of similar candidates, sorted by similarity (most similar first)
    """
    if not candidates:
        return []

    # Check for exact match (case-insensitive)
    query_lower = query.lower()
    for candidate in candidates:
        if candidate.lower() == query_lower:
            return []  # Exact match found, no suggestions needed

    # Calculate similarity scores for all candidates
    scored: list[tuple[str, float]] = []
    for candidate in candidates:
        score = similarity_score(query, candidate)
        if score >= threshold:
            scored.append((candidate, score))

    # Sort by similarity (descending), then by name (for stable ordering)
    scored.sort(key=lambda x: (-x[1], x[0]))

    # Return top suggestions
    return [candidate for candidate, _ in scored[:max_suggestions]]
