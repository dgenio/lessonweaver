"""Public API stability guardrails."""

from __future__ import annotations

import json
from pathlib import Path

import lessonweaver


def _snapshot() -> list[str]:
    return json.loads(
        (Path(__file__).with_name("public_api_snapshot.json")).read_text(encoding="utf-8")
    )


def test_public_api_matches_checked_in_snapshot() -> None:
    assert sorted(lessonweaver.__all__) == _snapshot()


def test_api_stability_doc_covers_every_public_export() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    documented = set()
    for line in (repo_root / "docs" / "api-stability.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("| `"):
            documented.add(line.split("`", 2)[1])
    assert documented == set(_snapshot())
