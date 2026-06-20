"""Internal lexical helpers shared by retrieval, analysis, clustering, and lint."""

from __future__ import annotations

import re
from collections.abc import Iterable

TOKEN_RE = re.compile(r"[A-Za-z0-9_']+")

ANALYSIS_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "before",
        "for",
        "if",
        "in",
        "is",
        "it",
        "must",
        "not",
        "or",
        "the",
        "to",
        "when",
    }
)

# Clustering compares lesson-candidate prose, so it drops domain boilerplate
# words that are meaningful in skill instructions but noisy in candidate text.
CLUSTERING_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "based",
        "before",
        "candidate",
        "for",
        "if",
        "in",
        "is",
        "it",
        "lesson",
        "must",
        "not",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "when",
    }
)

# Retrieval-specific synonym expansion. Keep this explicit so domain shortcuts
# such as "PR" do not hide inside the tokenizer used by other modules.
QUERY_SYNONYMS: dict[str, set[str]] = {"pr": {"pull", "request", "requests"}}


def token_list(value: str) -> list[str]:
    """Return lowercase lexical tokens in source order."""
    return [token.lower() for token in TOKEN_RE.findall(value)]


def tokens(value: str, *, stopwords: Iterable[str] = ()) -> set[str]:
    """Return lowercase lexical tokens, optionally excluding stopwords."""
    stopword_set = set(stopwords)
    return {token for token in token_list(value) if token not in stopword_set}


def expand_query_synonyms(
    token_set: set[str], synonyms: dict[str, set[str]] = QUERY_SYNONYMS
) -> set[str]:
    """Return tokens plus retrieval-only synonyms for matched query terms."""
    expanded = set(token_set)
    for token in token_set:
        expanded.update(synonyms.get(token, set()))
    return expanded


def jaccard(left: set[str], right: set[str]) -> float:
    """Return Jaccard similarity for two token sets."""
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)
