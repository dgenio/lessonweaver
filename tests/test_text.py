"""Tests for internal lexical text utilities."""

from lessonweaver._text import (
    ANALYSIS_STOPWORDS,
    CLUSTERING_STOPWORDS,
    QUERY_SYNONYMS,
    expand_query_synonyms,
    jaccard,
    token_list,
    tokens,
)


def test_token_list_preserves_order_and_apostrophes() -> None:
    assert token_list("PR review: don't skip file_1") == [
        "pr",
        "review",
        "don't",
        "skip",
        "file_1",
    ]


def test_tokens_can_filter_named_stopwords() -> None:
    assert tokens("must inspect the policy", stopwords=ANALYSIS_STOPWORDS) == {
        "inspect",
        "policy",
    }
    assert "lesson" not in tokens("candidate lesson recurred", stopwords=CLUSTERING_STOPWORDS)


def test_jaccard_handles_empty_sets_and_overlap() -> None:
    assert jaccard(set(), {"a"}) == 0.0
    assert jaccard({"a", "b"}, {"b", "c"}) == 1 / 3


def test_query_synonym_expansion_is_explicit() -> None:
    assert QUERY_SYNONYMS["pr"] == {"pull", "request", "requests"}
    assert expand_query_synonyms({"review", "pr"}) == {
        "review",
        "pr",
        "pull",
        "request",
        "requests",
    }
