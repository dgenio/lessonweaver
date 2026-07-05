"""Tests for the changelog-fragment assembler (scripts/build_changelog.py, #343)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "build_changelog.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("build_changelog", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build_changelog = _load_module()


def _write_fragments(directory: Path, fragments: dict[str, str]) -> None:
    for name, body in fragments.items():
        (directory / name).write_text(body, encoding="utf-8")


def test_collect_fragments_groups_and_orders_by_filename(tmp_path: Path) -> None:
    _write_fragments(
        tmp_path,
        {
            "README.md": "# ignored",
            "2.added.md": "- Second added (#2).",
            "1.added.md": "- First added (#1).",
            "3.changed.md": "- A change (#3).",
        },
    )
    grouped = build_changelog.collect_fragments(tmp_path)
    # Sorted by filename within a category; README.md ignored.
    assert grouped["added"] == ["- First added (#1).", "- Second added (#2)."]
    assert grouped["changed"] == ["- A change (#3)."]
    assert grouped["fixed"] == []


def test_collect_fragments_rejects_bad_names(tmp_path: Path) -> None:
    _write_fragments(tmp_path, {"nodots.md": "- x"})
    with pytest.raises(ValueError, match="must be named"):
        build_changelog.collect_fragments(tmp_path)


def test_collect_fragments_rejects_unknown_category(tmp_path: Path) -> None:
    _write_fragments(tmp_path, {"12.improved.md": "- x"})
    with pytest.raises(ValueError, match="unknown category"):
        build_changelog.collect_fragments(tmp_path)


def test_render_section_uses_keep_a_changelog_order() -> None:
    grouped = {
        "added": ["- New thing (#1)."],
        "changed": ["- Changed thing (#2)."],
        "fixed": ["- Fixed thing (#3)."],
        "deprecated": [],
        "removed": [],
        "security": [],
    }
    section = build_changelog.render_section("0.5.0", "2026-07-05", grouped)
    assert section.startswith("## [0.5.0] - 2026-07-05\n")
    # Added before Changed before Fixed; empty categories omitted.
    assert section.index("### Added") < section.index("### Changed") < section.index("### Fixed")
    assert "### Removed" not in section


def test_build_changelog_inserts_section_after_unreleased(tmp_path: Path) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        "# Changelog\n\n## [Unreleased]\n\n## [0.4.1] - 2026-06-24\n\n### Added\n\n- Prior.\n",
        encoding="utf-8",
    )
    frag_dir = tmp_path / "changelog.d"
    frag_dir.mkdir()
    _write_fragments(frag_dir, {"342.changed.md": "- New behavior (#342)."})

    updated = build_changelog.build_changelog("0.5.0", "2026-07-05", changelog, frag_dir)

    assert "## [Unreleased]" in updated
    # New section sits between Unreleased and the prior release, preserving history.
    assert updated.index("## [Unreleased]") < updated.index("## [0.5.0] - 2026-07-05")
    assert updated.index("## [0.5.0] - 2026-07-05") < updated.index("## [0.4.1] - 2026-06-24")
    assert "- New behavior (#342)." in updated
    assert "- Prior." in updated
    # No run of 3+ newlines introduced by the insertion.
    assert "\n\n\n" not in updated


def test_build_changelog_is_deterministic(tmp_path: Path) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    contents = "# Changelog\n\n## [Unreleased]\n\n## [0.4.1] - 2026-06-24\n\n- Prior.\n"
    changelog.write_text(contents, encoding="utf-8")
    frag_dir = tmp_path / "changelog.d"
    frag_dir.mkdir()
    _write_fragments(
        frag_dir,
        {"9.added.md": "- Nine (#9).", "10.added.md": "- Ten (#10)."},
    )

    first = build_changelog.build_changelog("0.5.0", "2026-07-05", changelog, frag_dir)
    second = build_changelog.build_changelog("0.5.0", "2026-07-05", changelog, frag_dir)
    assert first == second
    # Filename sort is lexicographic: "10" precedes "9".
    assert first.index("- Ten (#10).") < first.index("- Nine (#9).")


def test_build_changelog_requires_fragments(tmp_path: Path) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("# Changelog\n\n## [Unreleased]\n", encoding="utf-8")
    frag_dir = tmp_path / "changelog.d"
    frag_dir.mkdir()
    (frag_dir / "README.md").write_text("# only readme", encoding="utf-8")
    with pytest.raises(ValueError, match="No changelog fragments"):
        build_changelog.build_changelog("0.5.0", "2026-07-05", changelog, frag_dir)
