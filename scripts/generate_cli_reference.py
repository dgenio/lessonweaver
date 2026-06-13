"""Generate the MkDocs CLI reference from the argparse command tree."""

from __future__ import annotations

import argparse
from pathlib import Path

from lessonweaver.cli import build_parser

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "reference" / "cli.md"


def render_cli_reference(parser: argparse.ArgumentParser | None = None) -> str:
    parser = parser or build_parser()
    subparsers = _subparsers(parser)
    lines = [
        "# CLI reference",
        "",
        "Generated from the `lessonweaver` argparse command tree. Update it with:",
        "",
        "```bash",
        "python scripts/generate_cli_reference.py",
        "```",
        "",
        "## Usage",
        "",
        "```text",
        parser.format_usage().strip(),
        "```",
        "",
        "## Subcommands",
        "",
    ]
    for command in sorted(subparsers.choices):
        command_parser = subparsers.choices[command]
        lines.extend(_render_command(command, command_parser))
    return "\n".join(lines).rstrip() + "\n"


def _subparsers(parser: argparse.ArgumentParser) -> argparse._SubParsersAction:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    raise ValueError("parser has no subcommands")


def _render_command(command: str, parser: argparse.ArgumentParser) -> list[str]:
    description = parser.description or ""
    if description == argparse.SUPPRESS:
        description = ""
    lines = [
        f"### `{command}`",
        "",
        description,
        "",
        "```text",
        parser.format_usage().strip(),
        "```",
        "",
    ]
    arguments = [_render_action(action) for action in parser._actions if action.dest != "help"]
    if arguments:
        lines.extend(["| Argument | Help |", "| --- | --- |"])
        lines.extend(arguments)
        lines.append("")
    return lines


def _render_action(action: argparse.Action) -> str:
    names = ", ".join(action.option_strings) if action.option_strings else action.dest
    help_text = (action.help or "").replace("|", "\\|")
    if action.required:
        help_text = f"{help_text} Required.".strip()
    return f"| `{names}` | {help_text} |"


def main(argv: list[str] | None = None) -> int:
    argv = argv or []
    rendered = render_cli_reference()
    if argv == ["--check"]:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != rendered:
            print(f"{OUTPUT} is out of date")
            return 1
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
