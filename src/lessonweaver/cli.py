"""lessonweaver command line interface."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
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
from .importers import candidates_from_failure_case
from .interview import LessonInterviewer, apply_review_answer, load_session, save_session
from .lint import LintSeverity, SkillLinter
from .models import (
    LessonCandidate,
    LessonStatus,
    OperationalLesson,
    RecommendedActionType,
    ReviewAnswer,
    ReviewSession,
    SensitivityLevel,
    SkillCard,
    SkillStatus,
    SkillUsageEvent,
)
from .privacy import SimpleRedactor
from .registry import FileSystemRegistry
from .reporting import SkillReporter
from .retrieval import RetrievalQuery, SkillRetriever
from .sanitization import TraceSanitizer
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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit_text(content: str, *, output: str | None, dry_run: bool) -> int:
    """Print ``content`` to stdout, or write it to ``output`` honoring ``--dry-run``.

    With ``--output`` set under ``--dry-run`` nothing is written; a notice is
    printed instead. Without ``--output`` the content always goes to stdout.
    """
    if output is not None:
        if dry_run:
            print(f"[dry-run] would write to: {output}")
        else:
            payload = content if content.endswith("\n") else content + "\n"
            Path(output).write_text(payload, encoding="utf-8")
    else:
        print(content)
    return 0


def _registry(root: str | None) -> FileSystemRegistry:
    return FileSystemRegistry(root)


def _emit_candidates(candidates: list[LessonCandidate], args: argparse.Namespace) -> int:
    """Optionally save candidates to the registry, then emit them as JSON.

    Shared by the ``detect`` and ``import-failure-case`` commands so both honor
    ``--save``, ``--dry-run``, and ``--output`` identically.
    """
    if args.save:
        if args.dry_run:
            print(
                f"[dry-run] would save {len(candidates)} candidate(s) to the registry",
                file=sys.stderr,
            )
        else:
            registry = _registry(args.registry_root)
            for candidate in candidates:
                registry.save_candidate(candidate)
    content = json.dumps(
        [candidate.to_dict() for candidate in candidates], indent=2, sort_keys=True
    )
    return _emit_text(content, output=args.output, dry_run=args.dry_run)


def _load_candidate_ref(candidate_ref: str, registry: FileSystemRegistry) -> LessonCandidate:
    path = Path(candidate_ref)
    if path.exists():
        return LessonCandidate.from_dict(_read_json(path))
    return registry.load_candidate(candidate_ref)


def _find_review_question(candidate: LessonCandidate, question_id: str):
    """Find a review question by id across both base and adaptive follow-up questions."""
    interviewer = LessonInterviewer()
    for question in interviewer.build_questions(candidate):
        if question.id == question_id:
            return question
    return interviewer.build_follow_up_questions(candidate).get(question_id)


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

    dry_run_parent = argparse.ArgumentParser(add_help=False)
    dry_run_parent.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the command without writing files or registry entries",
    )
    output_parent = argparse.ArgumentParser(add_help=False)
    output_parent.add_argument("--output", help="Write output to this file instead of stdout")

    subparsers = parser.add_subparsers(dest="command", required=True)

    detect_parser = subparsers.add_parser(
        "detect",
        parents=[dry_run_parent, output_parent],
        help="Detect lesson candidates from a trace JSON",
    )
    detect_parser.add_argument("trace_path")
    detect_parser.add_argument("--registry-root")
    detect_parser.add_argument(
        "--save", action="store_true", help="Save candidates to the registry"
    )
    detect_parser.add_argument(
        "--sanitize",
        action="store_true",
        help="Scrub sensitive content (email, bearer tokens, private keys) before detection",
    )

    failure_case_parser = subparsers.add_parser(
        "import-failure-case",
        parents=[dry_run_parent, output_parent],
        help="Detect lesson candidates from a replayable failure case artifact",
    )
    failure_case_parser.add_argument("artifact_path")
    failure_case_parser.add_argument("--registry-root")
    failure_case_parser.add_argument(
        "--save", action="store_true", help="Save candidates to the registry"
    )

    interview_parser = subparsers.add_parser(
        "interview",
        parents=[dry_run_parent],
        help="Generate review questions for a candidate",
    )
    interview_parser.add_argument("candidate")
    interview_parser.add_argument("--registry-root")
    interview_parser.add_argument(
        "--session", help="Write a new resumable review session to this path"
    )

    resume_parser = subparsers.add_parser(
        "resume-interview",
        parents=[dry_run_parent],
        help="Resume a saved review session and list the remaining questions",
    )
    resume_parser.add_argument("session_path")
    resume_parser.add_argument("--registry-root")

    answer_parser = subparsers.add_parser(
        "answer", help="Apply one MCQ review answer to a candidate"
    )
    answer_parser.add_argument("candidate_id")
    answer_parser.add_argument("question_id")
    answer_parser.add_argument("chosen_option_id")
    answer_parser.add_argument("--free-text", default="")
    answer_parser.add_argument("--registry-root")
    answer_parser.add_argument(
        "--session", help="Record this answer into a resumable review session at this path"
    )

    approve_parser = subparsers.add_parser(
        "approve",
        parents=[dry_run_parent],
        help="Approve a candidate into a lesson and skill",
    )
    approve_parser.add_argument("candidate_id")
    approve_parser.add_argument("--registry-root")
    approve_parser.add_argument("--approved-by")
    approve_parser.add_argument("--name")
    approve_parser.add_argument("--lesson-id")
    approve_parser.add_argument("--skill-id")

    export_parser = subparsers.add_parser(
        "export-skill",
        parents=[dry_run_parent, output_parent],
        help="Export a SkillCard",
    )
    export_parser.add_argument("skill")
    export_parser.add_argument(
        "--json",
        action="store_true",
        help='Wrap output in a {"format": ..., "content": ...} JSON envelope',
    )
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
        parents=[dry_run_parent, output_parent],
        help="Export an approved candidate as an eval, guardrail, or workflow artifact",
    )
    export_lesson_parser.add_argument("candidate")
    export_lesson_parser.add_argument(
        "--format", choices=["eval", "guardrail", "workflow"], required=True
    )
    export_lesson_parser.add_argument("--registry-root")
    export_lesson_parser.add_argument("--redact", action="store_true")
    export_lesson_parser.add_argument(
        "--json",
        action="store_true",
        help='Wrap output in a {"format": ..., "content": ...} JSON envelope',
    )

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

    usage_parser = subparsers.add_parser(
        "log-usage", help="Record that a skill was loaded into an agent context"
    )
    usage_parser.add_argument("skill_id")
    usage_parser.add_argument("task_context")
    usage_parser.add_argument("--skill-version", default="")
    usage_parser.add_argument("--outcome")
    outcome_group = usage_parser.add_mutually_exclusive_group()
    outcome_group.add_argument(
        "--positive", dest="outcome_positive", action="store_const", const=True, default=None
    )
    outcome_group.add_argument(
        "--negative", dest="outcome_positive", action="store_const", const=False
    )
    usage_parser.add_argument("--notes")
    usage_parser.add_argument("--id", dest="event_id")
    usage_parser.add_argument("--registry-root")

    report_parser = subparsers.add_parser(
        "report-stale",
        help="Report expired, deprecated, low-confidence, or never-used skills",
    )
    report_parser.add_argument("--registry-root")
    report_parser.add_argument(
        "--now", help="ISO 8601 timestamp to evaluate expiry against (default: current time)"
    )

    args = parser.parse_args(argv)

    try:
        return _run(args)
    except FileNotFoundError as exc:
        # Prefer the clean path from the OS error; registry lookups raise this
        # without a filename, so fall back to their explanatory message.
        location = exc.filename or str(exc)
        print(f"Error: file not found: {location}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(
            f"Error: invalid JSON: {exc.msg} (line {exc.lineno} column {exc.colno})",
            file=sys.stderr,
        )
        return 2
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


def _run(args: argparse.Namespace) -> int:
    if args.command == "detect":
        bundle = load_trace_bundle(args.trace_path)
        if args.sanitize:
            bundle = TraceSanitizer().sanitize(bundle)
        candidates = LessonDetector().detect(bundle)
        return _emit_candidates(candidates, args)

    if args.command == "import-failure-case":
        artifact = _read_json(args.artifact_path)
        candidates = candidates_from_failure_case(artifact)
        return _emit_candidates(candidates, args)

    if args.command == "interview":
        registry = _registry(args.registry_root)
        candidate = _load_candidate_ref(args.candidate, registry)
        questions = LessonInterviewer().build_questions(candidate)
        if args.session:
            # resume-interview reloads the candidate from the registry by id, so a
            # session is only resumable when its candidate is registry-backed.
            try:
                registry.load_candidate(candidate.id)
            except (FileNotFoundError, ValueError):
                print(
                    f"Error: interview --session requires a registry-backed candidate; "
                    f"'{candidate.id}' is not in the registry. Run `detect --save` first.",
                    file=sys.stderr,
                )
                return 1
            if args.dry_run:
                print(f"[dry-run] would write session to: {args.session}")
            else:
                created = _now_iso()
                session = ReviewSession(
                    session_id=f"session-{uuid.uuid4().hex}",
                    candidate_id=candidate.id,
                    started_at=created,
                    updated_at=created,
                )
                save_session(session, args.session)
        _print_json([question.to_dict() for question in questions])
        return 0

    if args.command == "resume-interview":
        session = load_session(args.session_path)
        if session.completed:
            print(
                f"Error: review session '{session.session_id}' is already completed "
                f"and cannot be resumed",
                file=sys.stderr,
            )
            return 1
        try:
            candidate = _registry(args.registry_root).load_candidate(session.candidate_id)
        except (FileNotFoundError, ValueError):
            print(
                f"Error: session '{session.session_id}' references candidate "
                f"'{session.candidate_id}', which is not in the registry; cannot resume.",
                file=sys.stderr,
            )
            return 1
        remaining = LessonInterviewer().next_questions(candidate, session.answers)
        if not args.dry_run:
            session.current_question_index = len(session.answers)
            session.updated_at = _now_iso()
            save_session(session, args.session_path)
        _print_json(
            {
                "session_id": session.session_id,
                "candidate_id": session.candidate_id,
                "current_question_index": session.current_question_index,
                "completed": session.completed,
                "remaining_questions": [question.to_dict() for question in remaining],
            }
        )
        return 0

    if args.command == "answer":
        registry = _registry(args.registry_root)
        candidate = registry.load_candidate(args.candidate_id)
        # Validate the target session up front so a bad session never leaves a
        # half-applied answer behind in the registry.
        review_session: ReviewSession | None = None
        if args.session:
            review_session = load_session(args.session)
            if review_session.completed:
                print(
                    f"Error: review session '{review_session.session_id}' is already completed "
                    f"and cannot record new answers",
                    file=sys.stderr,
                )
                return 1
            if review_session.candidate_id != candidate.id:
                print(
                    f"Error: session '{review_session.session_id}' is for candidate "
                    f"'{review_session.candidate_id}', not '{candidate.id}'",
                    file=sys.stderr,
                )
                return 1
        question = _find_review_question(candidate, args.question_id)
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
        if review_session is not None:
            review_session.answers.append(answer)
            review_session.current_question_index = len(review_session.answers)
            review_session.updated_at = _now_iso()
            save_session(review_session, args.session)
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
        if not args.dry_run:
            registry.save_candidate(approved)
            registry.save_lesson(lesson)
            registry.save_skill(skill)
        _print_json(
            {"candidate_id": approved.id, "lesson_id": lesson.lesson_id, "skill_id": skill.id}
        )
        return 0

    if args.command == "export-skill":
        skill = _load_skill_ref(args.skill, _registry(args.registry_root))
        content = _export_skill(skill, args.format, args.redact, args.applies_to)
        if args.json:
            content = json.dumps(
                {"format": args.format, "content": content}, indent=2, sort_keys=True
            )
        return _emit_text(content, output=args.output, dry_run=args.dry_run)

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
            content = export_eval_spec_markdown(candidate, redactor=redactor)
        elif args.format == "guardrail":
            content = export_guardrail_rule_markdown(candidate, redactor=redactor)
        else:
            content = export_workflow_recommendation_markdown(candidate, redactor=redactor)
        if args.json:
            content = json.dumps(
                {"format": args.format, "content": content}, indent=2, sort_keys=True
            )
        return _emit_text(content, output=args.output, dry_run=args.dry_run)

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

    if args.command == "log-usage":
        registry = _registry(args.registry_root)
        event = SkillUsageEvent(
            id=args.event_id or f"usage-{uuid.uuid4().hex}",
            skill_id=args.skill_id,
            skill_version=args.skill_version,
            task_context=args.task_context,
            outcome=args.outcome,
            outcome_positive=args.outcome_positive,
            notes=args.notes,
        )
        registry.save_usage_event(event)
        _print_json(event.to_dict())
        return 0

    if args.command == "report-stale":
        registry = _registry(args.registry_root)
        report_now: datetime | None = None
        if args.now:
            report_now = datetime.fromisoformat(args.now.replace("Z", "+00:00"))
            if report_now.tzinfo is None:
                report_now = report_now.replace(tzinfo=timezone.utc)
        reports = SkillReporter().report_stale(registry, now=report_now)
        _print_json([report.to_dict() for report in reports])
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
