"""Diff-first, idempotent insertion of exported skills into instruction files.

Exporters in :mod:`lessonweaver.export` produce text; this module decides how
that text lands in a real file (``.github/copilot-instructions.md``,
``CLAUDE.md``, ``AGENTS.md``, ...) without clobbering hand-written content. Each
managed skill is wrapped in HTML-comment sentinels keyed by skill id so a later
export of the same skill *updates in place* rather than appending a duplicate.

Writing is never implicit: callers render the merged text and a unified diff,
show the diff, and only persist when the user opts in. No file I/O happens here.
"""

from __future__ import annotations

import difflib
import re

_BEGIN = "<!-- lessonweaver:begin skill_id={skill_id} -->"
_END = "<!-- lessonweaver:end skill_id={skill_id} -->"


def _markers(skill_id: str) -> tuple[str, str]:
    return _BEGIN.format(skill_id=skill_id), _END.format(skill_id=skill_id)


def managed_block(content: str, skill_id: str) -> str:
    """Wrap exported ``content`` in id-keyed sentinels so it can be found later."""
    begin, end = _markers(skill_id)
    body = content.strip("\n")
    return f"{begin}\n{body}\n{end}\n"


def _block_pattern(skill_id: str) -> re.Pattern[str]:
    begin, end = _markers(skill_id)
    # Match an optional run of blank lines before the block so repeated updates
    # do not accumulate empty lines around it.
    return re.compile(
        rf"\n*{re.escape(begin)}.*?{re.escape(end)}\n?",
        re.DOTALL,
    )


def has_managed_block(existing: str, skill_id: str) -> bool:
    """Whether ``existing`` already contains a managed block for ``skill_id``."""
    return _block_pattern(skill_id).search(existing) is not None


def merge_managed_block(existing: str, content: str, skill_id: str) -> str:
    """Return ``existing`` with the managed block for ``skill_id`` upserted.

    If a block for this skill already exists it is replaced in place (preserving
    surrounding hand-written content); otherwise the block is appended after a
    blank-line separator. An empty ``existing`` yields just the block.
    """
    block = managed_block(content, skill_id)
    if not existing.strip():
        return block
    pattern = _block_pattern(skill_id)
    if pattern.search(existing):
        merged = pattern.sub("\n\n" + block, existing, count=1)
        return merged.lstrip("\n")
    separator = "" if existing.endswith("\n") else "\n"
    return f"{existing}{separator}\n{block}"


def diff_managed_file(existing: str, merged: str, path: str) -> str:
    """Return a unified diff from ``existing`` to ``merged`` for previewing."""
    diff = difflib.unified_diff(
        existing.splitlines(keepends=True),
        merged.splitlines(keepends=True),
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
    )
    return "".join(diff)
