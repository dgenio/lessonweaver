from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.10
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]


def _project_metadata() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]


def test_python_version_metadata_supports_310_through_314() -> None:
    project = _project_metadata()
    classifiers = set(project["classifiers"])

    assert project["requires-python"] == ">=3.10"
    for minor in ("10", "11", "12", "13", "14"):
        assert f"Programming Language :: Python :: 3.{minor}" in classifiers


def test_dependency_specifiers_are_library_friendly() -> None:
    project = _project_metadata()
    dependency_groups = [project.get("dependencies", [])]
    dependency_groups.extend(project.get("optional-dependencies", {}).values())

    for dependencies in dependency_groups:
        for requirement in dependencies:
            assert "==" not in requirement
            assert "<" not in requirement
            assert ">=" in requirement
