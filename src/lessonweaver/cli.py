"""lessonweaver command line interface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .detection import LessonDetector
from .export import (
    export_claude_skill_fragment,
    export_copilot_instruction_fragment,
    export_runtime_prompt_snippet,
    export_skillcard_json,
    export_skillcard_markdown,
)
from .interview import LessonInterviewer
from .models import LessonCandidate, SkillCard
from .traces import load_trace_bundle


def _read_json(path: str | Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lessonweaver")
    subparsers = parser.add_subparsers(dest="command", required=True)

    detect_parser = subparsers.add_parser("detect", help="Detect lesson candidates from a trace JSON")
    detect_parser.add_argument("trace_path")

    interview_parser = subparsers.add_parser("interview", help="Generate review questions for candidate JSON")
    interview_parser.add_argument("candidate_path")

    export_parser = subparsers.add_parser("export-skill", help="Export a SkillCard")
    export_parser.add_argument("skill_path")
    export_parser.add_argument(
        "--format",
        choices=["markdown", "json", "copilot", "claude", "runtime"],
        default="markdown",
    )

    args = parser.parse_args(argv)

    if args.command == "detect":
        bundle = load_trace_bundle(args.trace_path)
        candidates = LessonDetector().detect(bundle)
        print(json.dumps([candidate.to_dict() for candidate in candidates], indent=2))
        return 0

    if args.command == "interview":
        candidate = LessonCandidate.from_dict(_read_json(args.candidate_path))
        questions = LessonInterviewer().build_questions(candidate)
        print(json.dumps([question.to_dict() for question in questions], indent=2))
        return 0

    if args.command == "export-skill":
        skill = SkillCard.from_dict(_read_json(args.skill_path))
        if args.format == "markdown":
            print(export_skillcard_markdown(skill))
        elif args.format == "json":
            print(export_skillcard_json(skill))
        elif args.format == "copilot":
            print(export_copilot_instruction_fragment(skill))
        elif args.format == "claude":
            print(export_claude_skill_fragment(skill))
        else:
            print(export_runtime_prompt_snippet(skill))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
