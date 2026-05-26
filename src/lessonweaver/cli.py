"""lessonweaver command line interface."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .analysis import SkillAnalyzer
from .compile import InclusionLevel, SkillCompiler
from .detection import LessonDetector
from .export import (
    export_claude_skill_fragment,
    export_copilot_instruction_fragment,
    export_runtime_prompt_snippet,
    export_skillcard_json,
    export_skillcard_markdown,
)
from .governance import promote_skill
from .interview import LessonInterviewer, apply_review_answer
from .lint import LintSeverity, SkillLinter
from .models import (
    LessonCandidate,
    LessonStatus,
    OperationalLesson,
    ReviewAnswer,
    SensitivityLevel,
    SkillCard,
    SkillStatus,
)
from .privacy import SimpleRedactor
from .registry import FileSystemRegistry
from .retrieval import RetrievalQuery, SkillRetriever
from .traces import load_trace_bundle


def _read_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _print_json(payload: object) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _registry(root: str | None) -> FileSystemRegistry:
    return FileSystemRegistry(root)


def _load_candidate_ref(candidate_ref: str, registry: FileSystemRegistry) -> LessonCandidate:
    path = Path(candidate_ref)
    if path.exists():
        return LessonCandidate.from_dict(_read_json(path))
    return registry.load_candidate(candidate_ref)


def _load_skill_ref(skill_ref: str, registry: FileSystemRegistry) -> SkillCard:
    path = Path(skill_ref)
    if path.exists():
        return SkillCard.from_dict(_read_json(path))
    return registry.load_skill(skill_ref)


def _skill_from_candidate(
    candidate: LessonCandidate,
    *,
    skill_id: str,
    name: str,
    approved_by: str | None,
) -> SkillCard:
    now = datetime.now(timezone.utc)
    return SkillCard(
        id=skill_id,
        name=name,
        description=candidate.summary,
        applies_when=[candidate.summary],
        does_not_apply_when=["When the task is unrelated to the observed trace context."],
        instructions=[candidate.proposed_lesson],
        anti_patterns=[candidate.observed_problem],
        evidence_trace_ids=candidate.evidence_trace_ids,
        confidence=candidate.confidence,
        risk_level=candidate.risk_level,
        scope=candidate.scope,
        version="0.1.0",
        status=SkillStatus.APPROVED,
        sensitivity=SensitivityLevel.INTERNAL,
        owner=candidate.owner,
        approved_by=approved_by,
        created_at=now,
        updated_at=now,
        approved_at=now,
        metadata={"candidate_id": candidate.id},
    )


def _lesson_from_candidate(
    candidate: LessonCandidate,
    *,
    lesson_id: str,
    title: str,
) -> OperationalLesson:
    history = candidate.metadata.get("review_history", [])
    review_answers = [ReviewAnswer.from_dict(item) for item in history if isinstance(item, dict)]
    return OperationalLesson(
        lesson_id=lesson_id,
        candidate_id=candidate.id,
        title=title,
        summary=candidate.summary,
        instructions=[candidate.proposed_lesson],
        applies_when=[candidate.summary],
        does_not_apply_when=["When the task is unrelated to the observed trace context."],
        anti_patterns=[candidate.observed_problem],
        risk_level=candidate.risk_level,
        scope=candidate.scope,
        recommended_action_type=candidate.recommended_action_type,
        evidence_trace_ids=candidate.evidence_trace_ids,
        evidence_event_ids=candidate.evidence_event_ids,
        confidence=candidate.confidence,
        review_answers=review_answers,
        status=LessonStatus.APPROVED,
        approved_at=datetime.now(timezone.utc),
    )


def _export_skill(skill: SkillCard, fmt: str, redact: bool) -> str:
    redactor = SimpleRedactor() if redact else None
    if fmt == "markdown":
        return export_skillcard_markdown(skill, redactor=redactor)
    if fmt == "json":
        return export_skillcard_json(skill, redactor=redactor)
    if fmt in {"copilot", "copilot_instruction"}:
        return export_copilot_instruction_fragment(skill, redactor=redactor)
    if fmt in {"claude", "claude_skill"}:
        return export_claude_skill_fragment(skill, redactor=redactor)
    return export_runtime_prompt_snippet(skill, redactor=redactor)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lessonweaver")
    subparsers = parser.add_subparsers(dest="command", required=True)

    detect_parser = subparsers.add_parser(
        "detect", help="Detect lesson candidates from a trace JSON"
    )
    detect_parser.add_argument("trace_path")
    detect_parser.add_argument("--registry-root")
    detect_parser.add_argument(
        "--save", action="store_true", help="Save candidates to the registry"
    )

    interview_parser = subparsers.add_parser(
        "interview", help="Generate review questions for a candidate"
    )
    interview_parser.add_argument("candidate")
    interview_parser.add_argument("--registry-root")

    answer_parser = subparsers.add_parser(
        "answer", help="Apply one MCQ review answer to a candidate"
    )
    answer_parser.add_argument("candidate_id")
    answer_parser.add_argument("question_id")
    answer_parser.add_argument("chosen_option_id")
    answer_parser.add_argument("--free-text", default="")
    answer_parser.add_argument("--registry-root")

    approve_parser = subparsers.add_parser(
        "approve", help="Approve a candidate into a lesson and skill"
    )
    approve_parser.add_argument("candidate_id")
    approve_parser.add_argument("--registry-root")
    approve_parser.add_argument("--approved-by")
    approve_parser.add_argument("--name")
    approve_parser.add_argument("--lesson-id")
    approve_parser.add_argument("--skill-id")

    export_parser = subparsers.add_parser("export-skill", help="Export a SkillCard")
    export_parser.add_argument("skill")
    export_parser.add_argument(
        "--format",
        choices=[
            "markdown",
            "json",
            "copilot",
            "copilot_instruction",
            "claude",
            "claude_skill",
            "runtime",
        ],
        default="markdown",
    )
    export_parser.add_argument("--registry-root")
    export_parser.add_argument("--redact", action="store_true")

    lint_parser = subparsers.add_parser("lint", help="Lint a SkillCard")
    lint_parser.add_argument("skill")
    lint_parser.add_argument("--registry-root")

    analyze_parser = subparsers.add_parser(
        "analyze-skills", help="Analyze a directory of skill JSON files"
    )
    analyze_parser.add_argument("skills_dir")

    retrieve_parser = subparsers.add_parser("retrieve", help="Retrieve relevant active skills")
    retrieve_parser.add_argument("task")
    retrieve_parser.add_argument("--registry-root")
    retrieve_parser.add_argument("--scope", default="")
    retrieve_parser.add_argument("--risk-level", default="")
    retrieve_parser.add_argument("--max", type=int, default=10)

    load_parser = subparsers.add_parser(
        "load", help="Compile relevant skills into a prompt snippet"
    )
    load_parser.add_argument("task")
    load_parser.add_argument("--registry-root")
    load_parser.add_argument("--scope", default="")
    load_parser.add_argument("--risk-level", default="")
    load_parser.add_argument("--budget-chars", type=int, default=2000)
    load_parser.add_argument("--max-skills", type=int, default=10)
    load_parser.add_argument(
        "--inclusion-level", choices=[item.value for item in InclusionLevel], default="summary"
    )

    promote_parser = subparsers.add_parser(
        "promote-skill", help="Promote a skill through the governed lifecycle"
    )
    promote_parser.add_argument("skill_id")
    promote_parser.add_argument("target", choices=[item.value for item in SkillStatus])
    promote_parser.add_argument("--registry-root")

    args = parser.parse_args(argv)

    if args.command == "detect":
        bundle = load_trace_bundle(args.trace_path)
        candidates = LessonDetector().detect(bundle)
        if args.save:
            registry = _registry(args.registry_root)
            for candidate in candidates:
                registry.save_candidate(candidate)
        _print_json([candidate.to_dict() for candidate in candidates])
        return 0

    if args.command == "interview":
        candidate = _load_candidate_ref(args.candidate, _registry(args.registry_root))
        questions = LessonInterviewer().build_questions(candidate)
        _print_json([question.to_dict() for question in questions])
        return 0

    if args.command == "answer":
        registry = _registry(args.registry_root)
        candidate = registry.load_candidate(args.candidate_id)
        question = next(
            (
                question
                for question in LessonInterviewer().build_questions(candidate)
                if question.id == args.question_id
            ),
            None,
        )
        if question is None:
            print(f"question '{args.question_id}' not found", file=sys.stderr)
            return 1
        answer = ReviewAnswer(args.question_id, args.chosen_option_id, args.free_text)
        try:
            updated_candidate = apply_review_answer(candidate, question, answer)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        registry.save_candidate(updated_candidate)
        _print_json(updated_candidate.to_dict())
        return 0

    if args.command == "approve":
        registry = _registry(args.registry_root)
        candidate = registry.load_candidate(args.candidate_id)
        now = datetime.now(timezone.utc)
        approved = replace(
            candidate,
            status=LessonStatus.APPROVED,
            approved_by=args.approved_by,
            approved_at=now,
            updated_at=now,
        )
        title = args.name or approved.summary
        lesson_id = args.lesson_id or f"lesson-{approved.id}"
        skill_id = args.skill_id or f"skill-{approved.id}"
        lesson = _lesson_from_candidate(approved, lesson_id=lesson_id, title=title)
        skill = _skill_from_candidate(
            approved, skill_id=skill_id, name=title, approved_by=args.approved_by
        )
        registry.save_candidate(approved)
        registry.save_lesson(lesson)
        registry.save_skill(skill)
        _print_json(
            {"candidate_id": approved.id, "lesson_id": lesson.lesson_id, "skill_id": skill.id}
        )
        return 0

    if args.command == "export-skill":
        skill = _load_skill_ref(args.skill, _registry(args.registry_root))
        print(_export_skill(skill, args.format, args.redact))
        return 0

    if args.command == "lint":
        skill = _load_skill_ref(args.skill, _registry(args.registry_root))
        lint_findings = SkillLinter().lint(skill)
        for lint_finding in lint_findings:
            print(
                f"[{lint_finding.severity.value.upper()}] "
                f"{lint_finding.rule_id}: {lint_finding.message}"
            )
        return (
            1
            if any(lint_finding.severity is LintSeverity.ERROR for lint_finding in lint_findings)
            else 0
        )

    if args.command == "analyze-skills":
        skills = [
            SkillCard.from_dict(_read_json(path))
            for path in sorted(Path(args.skills_dir).glob("*.json"))
        ]
        analysis_findings = SkillAnalyzer().analyze(skills)
        for analysis_finding in analysis_findings:
            print(
                f"[{analysis_finding.finding_type}] "
                f"{analysis_finding.skill_id_a} <-> {analysis_finding.skill_id_b}: "
                f"{analysis_finding.reason} ({analysis_finding.confidence:.2f})"
            )
        return 0

    if args.command == "retrieve":
        registry = _registry(args.registry_root)
        results = SkillRetriever().retrieve(
            registry.list_skills(),
            RetrievalQuery(
                task=args.task,
                scope=args.scope,
                risk_level=args.risk_level,
                max_results=args.max,
            ),
        )
        _print_json(
            [
                {
                    "skill_id": result.skill.id,
                    "score": result.score,
                    "match_reason": result.match_reason,
                }
                for result in results
            ]
        )
        return 0

    if args.command == "load":
        registry = _registry(args.registry_root)
        results = SkillRetriever().retrieve(
            registry.list_skills(),
            RetrievalQuery(
                task=args.task,
                scope=args.scope,
                risk_level=args.risk_level,
                max_results=args.max_skills,
            ),
        )
        context = SkillCompiler().compile(
            results,
            budget_chars=args.budget_chars,
            default_inclusion=InclusionLevel(args.inclusion_level),
        )
        _print_json(
            {
                "snippet": context.snippet,
                "included_skills": context.included_skills,
                "omitted_skills": context.omitted_skills,
                "total_chars": context.total_chars,
            }
        )
        return 0

    if args.command == "promote-skill":
        registry = _registry(args.registry_root)
        skill = registry.load_skill(args.skill_id)
        promoted = promote_skill(skill, SkillStatus(args.target))
        registry.save_skill(promoted)
        _print_json(promoted.to_dict())
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
