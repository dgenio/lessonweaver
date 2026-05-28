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
    export_agents_md_fragment,
    export_claude_md_snippet,
    export_claude_rule_fragment,
    export_claude_skill_fragment,
    export_claude_skill_md,
    export_codex_skill_directory,
    export_copilot_instruction_fragment,
    export_copilot_path_instruction,
    export_copilot_repo_instruction,
    export_eval_spec_markdown,
    export_guardrail_rule_markdown,
    export_runtime_prompt_snippet,
    export_skillcard_json,
    export_skillcard_markdown,
    export_workflow_recommendation_markdown,
)
from .governance import promote_skill
from .interview import LessonInterviewer, apply_review_answer
from .lint import LintSeverity, SkillLinter
from .models import (
    LessonCandidate,
    LessonStatus,
    OperationalLesson,
    RecommendedActionType,
    ReviewAnswer,
    SensitivityLevel,
    SkillCard,
    SkillStatus,
)
from .privacy import SimpleRedactor
from .registry import FileSystemRegistry
from .retrieval import RetrievalQuery, SkillRetriever
from .traces import load_trace_bundle
from .validation import ValidationSuite, run_validation_suite


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


def _load_skill_cards_from_dir(skills_dir: str) -> list[SkillCard]:
    """Load every SkillCard JSON in a directory.

    Non-SkillCard JSON files (e.g. a candidate or validation-suite fixture that
    lives alongside a skill in a worked-example folder) are skipped rather than
    parsed, so pointing ``--skills-dir`` at such a folder does not crash. A
    SkillCard is identified by the required ``name`` key; files that look like a
    skill but fail to parse still raise, surfacing genuinely malformed skills.
    """
    skills: list[SkillCard] = []
    for path in sorted(Path(skills_dir).glob("*.json")):
        data = _read_json(path)
        if "name" not in data:
            continue
        skills.append(SkillCard.from_dict(data))
    return skills


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


def _export_skill(skill: SkillCard, fmt: str, redact: bool, applies_to: str = "**") -> str:
    redactor = SimpleRedactor() if redact else None
    if fmt == "markdown":
        return export_skillcard_markdown(skill, redactor=redactor)
    if fmt == "json":
        return export_skillcard_json(skill, redactor=redactor)
    if fmt in {"copilot", "copilot_instruction"}:
        return export_copilot_instruction_fragment(skill, redactor=redactor)
    if fmt == "copilot-repo":
        return export_copilot_repo_instruction(skill, redactor=redactor)
    if fmt == "copilot-path":
        return export_copilot_path_instruction(skill, applies_to, redactor=redactor)
    if fmt in {"claude", "claude_skill"}:
        return export_claude_skill_fragment(skill, redactor=redactor)
    if fmt == "claude-skill":
        return export_claude_skill_md(skill, redactor=redactor)
    if fmt == "claude-rule":
        return export_claude_rule_fragment(skill, redactor=redactor)
    if fmt == "claude-md":
        return export_claude_md_snippet(skill, redactor=redactor)
    if fmt == "agents-md":
        return export_agents_md_fragment(skill, redactor=redactor)
    if fmt == "codex":
        directory = export_codex_skill_directory(skill, redactor=redactor)
        return json.dumps(directory, indent=2, sort_keys=True)
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
            "copilot-repo",
            "copilot-path",
            "claude",
            "claude_skill",
            "claude-skill",
            "claude-rule",
            "claude-md",
            "agents-md",
            "codex",
            "runtime",
        ],
        default="markdown",
    )
    export_parser.add_argument(
        "--applies-to",
        default="**",
        help="Glob for the copilot-path applyTo frontmatter (default: **)",
    )
    export_parser.add_argument("--registry-root")
    export_parser.add_argument("--redact", action="store_true")

    export_lesson_parser = subparsers.add_parser(
        "export-lesson",
        help="Export an approved candidate as an eval, guardrail, or workflow artifact",
    )
    export_lesson_parser.add_argument("candidate")
    export_lesson_parser.add_argument(
        "--format", choices=["eval", "guardrail", "workflow"], required=True
    )
    export_lesson_parser.add_argument("--registry-root")
    export_lesson_parser.add_argument("--redact", action="store_true")

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

    validate_parser = subparsers.add_parser(
        "validate-skill",
        help="Validate that a skill retrieves correctly for a validation suite",
    )
    validate_parser.add_argument("suite")
    validate_skills_source = validate_parser.add_mutually_exclusive_group()
    validate_skills_source.add_argument(
        "--skills-dir",
        help="Directory of skill JSON files to validate against (default: registry)",
    )
    validate_skills_source.add_argument(
        "--registry-root",
        help="Registry root containing the skills/ directory (default: ~/.lessonweaver/registry)",
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
        print(_export_skill(skill, args.format, args.redact, args.applies_to))
        return 0

    if args.command == "export-lesson":
        candidate = _load_candidate_ref(args.candidate, _registry(args.registry_root))
        if candidate.status is not LessonStatus.APPROVED:
            print(
                f"candidate '{candidate.id}' is not approved "
                f"(status: {candidate.status.value}); approve it before exporting",
                file=sys.stderr,
            )
            return 1
        expected_action = {
            "eval": RecommendedActionType.EVAL,
            "guardrail": RecommendedActionType.GUARDRAIL,
            "workflow": RecommendedActionType.WORKFLOW_CHANGE,
        }[args.format]
        if candidate.recommended_action_type is not expected_action:
            print(
                f"candidate '{candidate.id}' has action type "
                f"'{candidate.recommended_action_type.value}'; cannot export as "
                f"'{args.format}' (expected '{expected_action.value}')",
                file=sys.stderr,
            )
            return 1
        redactor = SimpleRedactor() if args.redact else None
        if args.format == "eval":
            print(export_eval_spec_markdown(candidate, redactor=redactor))
        elif args.format == "guardrail":
            print(export_guardrail_rule_markdown(candidate, redactor=redactor))
        else:
            print(export_workflow_recommendation_markdown(candidate, redactor=redactor))
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
        skills = _load_skill_cards_from_dir(args.skills_dir)
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

    if args.command == "validate-skill":
        suite = ValidationSuite.from_dict(_read_json(args.suite))
        if args.skills_dir:
            skills = _load_skill_cards_from_dir(args.skills_dir)
        else:
            skills = _registry(args.registry_root).list_skills()
        if not any(skill.id == suite.skill_id for skill in skills):
            print(
                f"warning: suite skill_id '{suite.skill_id}' not found among "
                f"{len(skills)} loaded skill(s); positive examples without an "
                f"expected_skill_id override will be false negatives",
                file=sys.stderr,
            )
        result = run_validation_suite(suite, skills)
        _print_json(result.to_dict())
        return 0 if result.failed == 0 else 1

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
