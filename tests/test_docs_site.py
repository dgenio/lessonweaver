from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
from types import ModuleType

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _load_cli_reference_script() -> ModuleType:
    script_path = ROOT / "scripts" / "generate_cli_reference.py"
    spec = importlib.util.spec_from_file_location("generate_cli_reference", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_docs_optional_dependencies_include_site_tooling() -> None:
    pyproject = tomllib.loads(_text("pyproject.toml"))

    docs_deps = pyproject["project"]["optional-dependencies"]["docs"]

    assert "mkdocs-material" in docs_deps
    assert "mkdocstrings[python]" in docs_deps
    assert "mike" in docs_deps


def test_mkdocs_config_enables_material_navigation_api_cli_and_mermaid() -> None:
    config = _text("mkdocs.yml")

    assert "site_name: lessonweaver" in config
    assert "name: material" in config
    assert "mkdocstrings" in config
    assert "pymdownx.superfences" in config
    assert "name: mermaid" in config
    assert "API Reference: reference/api.md" in config
    assert "CLI Reference: reference/cli.md" in config
    assert "Developer workflow: developer-workflow.md" in config


def test_api_reference_lists_every_public_export() -> None:
    from lessonweaver import __all__ as public_exports

    api_reference = _text("docs/reference/api.md")

    assert "::: lessonweaver" in api_reference
    for name in public_exports:
        assert f"      - {name}" in api_reference


def test_cli_reference_generator_documents_every_subcommand() -> None:
    from lessonweaver.cli import build_parser

    parser = build_parser()
    subparsers = next(
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    )
    rendered = _load_cli_reference_script().render_cli_reference(parser)

    assert "# CLI reference" in rendered
    for command in sorted(subparsers.choices):
        assert f"### `{command}`" in rendered
    assert "--dry-run" in rendered
    assert "--registry-root" in rendered


def test_docs_workflow_builds_strict_site_and_deploys_pages() -> None:
    workflow = _text(".github/workflows/docs.yml")

    assert "mkdocs build --strict" in workflow
    assert "python scripts/generate_cli_reference.py --check" in workflow
    assert "actions/configure-pages" in workflow
    assert "actions/upload-pages-artifact" in workflow
    assert "actions/deploy-pages" in workflow
