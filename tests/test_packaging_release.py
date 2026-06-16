from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_packaging_metadata_supports_public_pypi_install() -> None:
    pyproject = tomllib.loads(_text("pyproject.toml"))

    project = pyproject["project"]
    assert project["name"] == "lessonweaver"
    assert project["description"]
    assert project["license"] == "Apache-2.0"
    assert "Programming Language :: Python :: 3.10" in project["classifiers"]
    assert "Typing :: Typed" in project["classifiers"]
    assert pyproject["project"]["urls"]["Repository"] == "https://github.com/dgenio/lessonweaver"
    assert pyproject["project"]["scripts"]["lessonweaver"] == "lessonweaver.cli:main"
    assert pyproject["tool"]["setuptools"]["package-data"]["lessonweaver"] == ["py.typed"]
    assert "build>=1.0" in project["optional-dependencies"]["dev"]
    assert "twine>=6.1" in project["optional-dependencies"]["dev"]


def test_readme_quickstart_distinguishes_user_and_contributor_installs() -> None:
    readme = _text("README.md")
    quickstart = readme.split("## Quickstart", 1)[1].split("## Runtime loading", 1)[0]

    assert "pip install lessonweaver" in quickstart
    assert 'pip install -e ".[dev]"' in quickstart
    assert "lessonweaver detect examples/traces/github_pr_review_failure.json" in quickstart
    assert "first PyPI release is being prepared" not in quickstart
    assert "Once published" not in quickstart


def test_release_checklist_verifies_build_artifacts_and_installed_cli() -> None:
    release_doc = _text("docs/release.md")

    assert "python -m build" in release_doc
    assert "twine check dist/*" in release_doc
    assert "lessonweaver/py.typed" in release_doc
    assert "python -m pip install --force-reinstall dist/" in release_doc
    assert "lessonweaver --help" in release_doc
    assert "TestPyPI" in release_doc
    assert "GitHub Release" in release_doc
