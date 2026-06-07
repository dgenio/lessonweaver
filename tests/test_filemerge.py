"""Tests for diff-first managed-block file merging."""

from lessonweaver.filemerge import (
    diff_managed_file,
    has_managed_block,
    managed_block,
    merge_managed_block,
)


def test_managed_block_wraps_content_in_id_keyed_sentinels() -> None:
    block = managed_block("hello", "skill-1")
    assert block.startswith("<!-- lessonweaver:begin skill_id=skill-1 -->\n")
    assert block.endswith("<!-- lessonweaver:end skill_id=skill-1 -->\n")
    assert "hello" in block


def test_merge_into_empty_file_is_just_the_block() -> None:
    merged = merge_managed_block("", "body", "skill-1")
    assert merged == managed_block("body", "skill-1")


def test_merge_appends_and_preserves_handwritten_content() -> None:
    existing = "# My instructions\n\nHand-written guidance.\n"
    merged = merge_managed_block(existing, "body", "skill-1")
    assert merged.startswith(existing)
    assert has_managed_block(merged, "skill-1")
    assert "Hand-written guidance." in merged


def test_merge_updates_existing_block_in_place_without_duplicating() -> None:
    first = merge_managed_block("preamble\n", "v1 body", "skill-1")
    second = merge_managed_block(first, "v2 body", "skill-1")
    assert "v1 body" not in second
    assert "v2 body" in second
    assert second.count("lessonweaver:begin skill_id=skill-1") == 1
    assert "preamble" in second


def test_merge_is_idempotent_for_unchanged_content() -> None:
    once = merge_managed_block("preamble\n", "body", "skill-1")
    twice = merge_managed_block(once, "body", "skill-1")
    assert once == twice


def test_distinct_skills_coexist_as_separate_blocks() -> None:
    merged = merge_managed_block("", "a", "skill-1")
    merged = merge_managed_block(merged, "b", "skill-2")
    assert has_managed_block(merged, "skill-1")
    assert has_managed_block(merged, "skill-2")


def test_diff_managed_file_reports_no_diff_for_identical_text() -> None:
    assert diff_managed_file("same\n", "same\n", "AGENTS.md") == ""


def test_diff_managed_file_shows_added_lines() -> None:
    diff = diff_managed_file("", managed_block("body", "skill-1"), "AGENTS.md")
    assert "+++ b/AGENTS.md" in diff
    assert "+body" in diff
