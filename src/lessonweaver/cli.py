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
from .cleanup import SkillCleaner
from .clustering import DEFAULT_SIMILARITY_THRESHOLD, LessonClusterer
from .compile import InclusionLevel, SkillCompiler
from .detection import LessonDetector
from .detection_eval import DetectionCorpus, run_detection_eval
from .diagnostics import explain_load
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
from .filemerge import diff_managed_file, merge_managed_block
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
from .prdiff import apply_file_change, plan_coding_agent_change
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


def _parse_now(value: str | None) -> datetime | None:
    """Parse an ISO 8601 ``--now`` override into an aware datetime (UTC if naive)."""
    if not value:
        return None
    moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment


def _parse_kv(items: list[str]) -> dict[str, str]:
    """Parse repeated ``KEY=VALUE`` CLI flags into a dict, preserving order."""
    parsed: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"expected KEY=VALUE, got '{item}'")
        key, _, value = item.partition("=")
        parsed[key.strip()] = value
    return parsed


def _remaining_review_questions(candidate: LessonCandidate) -> list[str]:
    """Return the ids of required review questions still unanswered for a candidate.

    The adaptive interviewer is the single source of truth for what "complete"
    means: a ``reject`` decision drops scoping questions, and ``high`` risk or a
    ``workflow_change`` action queues follow-ups. An empty list means the review
    gate is satisfied.
    """
    history = candidate.metadata.get("review_history", [])
    answers = [ReviewAnswer.from_dict(item) for item in history if isinstance(item, dict)]
    return [question.id for question in LessonInterviewer().next_questions(candidate, answers)]


def _apply_answers(
    candidate: LessonCandidate,
    answers: dict[str, str],
    free_text: dict[str, str],
) -> LessonCandidate:
    """Apply ``question=option`` answers (with optional free text) to a candidate."""
    for question_id, option_id in answers.items():
        question = _find_review_question(candidate, question_id)
        if question is None:
            raise ValueError(f"question '{question_id}' not found")
        answer = ReviewAnswer(question_id, option_id, free_text.get(question_id, ""))
        candidate = apply_review_answer(candidate, question, answer)
    return candidate


def _do_approve(
    candidate: LessonCandidate,
    registry: FileSystemRegistry,
    *,
    approved_by: str | None,
    name: str | None = None,
    lesson_id: str | None = None,
    skill_id: str | None = None,
    allow_incomplete: bool = False,
    dry_run: bool = False,
) -> tuple[dict[str, str] | None, list[str]]:
    """Approve a candidate into a lesson and skill, enforcing the review gate.

    Returns ``(result, [])`` on success or ``(None, missing_questions)`` when the
    review is incomplete and the override was not requested. When the override is
    used, the unanswered questions are recorded on the lesson candidate and skill
    metadata so the bypass is auditable.
    """
    remaining = _remaining_review_questions(candidate)
    if remaining and not allow_incomplete:
        return None, remaining

    now = datetime.now(timezone.utc)
    approved = replace(
        candidate,
        status=LessonStatus.APPROVED,
        approved_by=approved_by,
        approved_at=now,
        updated_at=now,
    )
    title = name or approved.summary
    lesson_id = lesson_id or f"lesson-{approved.id}"
    skill_id = skill_id or f"skill-{approved.id}"
    lesson = _lesson_from_candidate(approved, lesson_id=lesson_id, title=title)
    skill = _skill_from_candidate(approved, skill_id=skill_id, name=title, approved_by=approved_by)

    if remaining and allow_incomplete:
        override = {
            "unanswered_questions": remaining,
            "approved_by": approved_by,
            "approved_at": now.isoformat(),
        }
        approved.metadata["incomplete_review_override"] = override
        skill.metadata["incomplete_review_override"] = override

    if not dry_run:
        registry.save_candidate(approved)
        registry.save_lesson(lesson)
        registry.save_skill(skill)
    return {"candidate_id": approved.id, "lesson_id": lesson.lesson_id, "skill_id": skill.id}, []


def _review_packet(candidate: LessonCandidate, args: argparse.Namespace) -> dict[str, Any]:
    """Build the guided-review summary for one candidate (questions, lint, preview)."""
    remaining = _remaining_review_questions(candidate)
    skill = _skill_from_candidate(
        candidate,
        skill_id=f"skill-{candidate.id}",
        name=candidate.summary,
        approved_by=getattr(args, "approved_by", None),
    )
    lint_findings = SkillLinter().lint(skill)
    packet: dict[str, Any] = {
        "candidate_id": candidate.id,
        "summary": candidate.summary,
        "observed_problem": candidate.observed_problem,
        "evidence_trace_ids": candidate.evidence_trace_ids,
        "status": candidate.status.value,
        "remaining_questions": remaining,
        "review_complete": not remaining,
        "lint": [
            f"[{finding.severity.value.upper()}] {finding.rule_id}: {finding.message}"
            for finding in lint_findings
        ],
    }
    target = getattr(args, "target", None)
    if target:
        packet["export_preview"] = {
            "format": target,
            "content": _export_skill(skill, target, args.redact, args.applies_to),
        }
    return packet


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

    cluster_parser = subparsers.add_parser(
        "cluster",
        help="Detect candidates across multiple traces and group recurring patterns",
    )
    cluster_parser.add_argument("trace_paths", nargs="+")
    cluster_parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_SIMILARITY_THRESHOLD,
        help="Jaccard similarity threshold to group candidates (default: 0.4)",
    )
    cluster_parser.add_argument(
        "--sanitize",
        action="store_true",
        help="Scrub sensitive content (email, bearer tokens, private keys) before detection",
    )

    eval_detection_parser = subparsers.add_parser(
        "eval-detection",
        help="Score detection precision/recall/F1 against a labeled trace corpus",
    )
    eval_detection_parser.add_argument("corpus_path")
    eval_detection_parser.add_argument(
        "--min-precision",
        type=float,
        help="Exit non-zero if precision falls below this floor (CI gate)",
    )
    eval_detection_parser.add_argument(
        "--min-recall",
        type=float,
        help="Exit non-zero if recall falls below this floor (CI gate)",
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
    approve_parser.add_argument(
        "--allow-incomplete-review",
        action="store_true",
        help="Override the review gate; records the unanswered questions in metadata",
    )

    review_trace_parser = subparsers.add_parser(
        "review-trace",
        parents=[dry_run_parent],
        help="Guided detect -> review -> (approve) workflow for a single trace",
    )
    review_trace_parser.add_argument("trace_path")
    review_trace_parser.add_argument("--registry-root")
    review_trace_parser.add_argument(
        "--candidate",
        help="Focus a single detected candidate id (required to answer/approve when a "
        "trace yields more than one candidate)",
    )
    review_trace_parser.add_argument(
        "--answer",
        action="append",
        default=[],
        metavar="QUESTION=OPTION",
        help="Apply an MCQ answer, e.g. --answer decision=approve (repeatable)",
    )
    review_trace_parser.add_argument(
        "--free-text",
        action="append",
        default=[],
        metavar="QUESTION=TEXT",
        help="Attach reviewer free text to a question, e.g. --free-text scope=team (repeatable)",
    )
    review_trace_parser.add_argument(
        "--approve",
        action="store_true",
        help="Approve the focused candidate after applying answers (enforces the review gate)",
    )
    review_trace_parser.add_argument("--approved-by")
    review_trace_parser.add_argument("--allow-incomplete-review", action="store_true")
    review_trace_parser.add_argument(
        "--target", help="Preview an export of the resulting skill in this format"
    )
    review_trace_parser.add_argument("--applies-to", default="**")
    review_trace_parser.add_argument("--redact", action="store_true")
    review_trace_parser.add_argument(
        "--sanitize",
        action="store_true",
        help="Scrub sensitive content (email, bearer tokens, private keys) before detection",
    )

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

    export_file_parser = subparsers.add_parser(
        "export-file",
        parents=[dry_run_parent],
        help="Merge a skill into an instruction file as a reviewable diff (idempotent block)",
    )
    export_file_parser.add_argument("skill")
    export_file_parser.add_argument(
        "--path", required=True, help="Target instruction file to create or update"
    )
    export_file_parser.add_argument(
        "--format",
        choices=[
            "markdown",
            "copilot",
            "copilot-repo",
            "copilot-path",
            "claude",
            "claude-skill",
            "claude-rule",
            "claude-md",
            "agents-md",
            "runtime",
        ],
        default="agents-md",
    )
    export_file_parser.add_argument(
        "--applies-to",
        default="**",
        help="Glob for the copilot-path applyTo frontmatter (default: **)",
    )
    export_file_parser.add_argument(
        "--redact",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Redact before writing (default: on; pass --no-redact to disable)",
    )
    export_file_parser.add_argument(
        "--write",
        action="store_true",
        help="Write the merged file (default: preview the diff only)",
    )
    export_file_parser.add_argument("--registry-root")

    pr_diff_parser = subparsers.add_parser(
        "generate-pr-diff",
        parents=[dry_run_parent],
        help="Generate PR-ready local file changes for an approved lesson artifact",
    )
    pr_diff_parser.add_argument("candidate")
    pr_diff_parser.add_argument(
        "--target",
        choices=["coding-agent"],
        default="coding-agent",
        help="Framework target to generate (default: coding-agent)",
    )
    pr_diff_parser.add_argument(
        "--path",
        default="AGENTS.md",
        help="Target file to create or update (default: AGENTS.md)",
    )
    pr_diff_parser.add_argument(
        "--write",
        action="store_true",
        help="Write the merged file (default: preview the diff only)",
    )
    pr_diff_parser.add_argument("--registry-root")

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
    load_parser.add_argument("--agent-type", default="")
    load_parser.add_argument("--tools", nargs="*", default=[])
    load_parser.add_argument("--scope", default="")
    load_parser.add_argument("--risk-level", default="")
    load_parser.add_argument("--budget-chars", type=int, default=2000)
    load_parser.add_argument("--max-skills", type=int, default=10)
    load_parser.add_argument(
        "--inclusion-level", choices=[item.value for item in InclusionLevel], default="summary"
    )
    load_parser.add_argument(
        "--explain",
        action="store_true",
        help="Explain which skills loaded or were skipped, with reason codes and budget usage",
    )

    explain_load_parser = subparsers.add_parser(
        "explain-load",
        help="Explain which skills load for a task and why (loaded, skipped, budget, overlaps)",
    )
    explain_load_parser.add_argument("task")
    explain_load_parser.add_argument("--registry-root")
    explain_load_parser.add_argument("--agent-type", default="")
    explain_load_parser.add_argument("--tools", nargs="*", default=[])
    explain_load_parser.add_argument("--scope", default="")
    explain_load_parser.add_argument("--risk-level", default="")
    explain_load_parser.add_argument("--budget-chars", type=int, default=2000)
    explain_load_parser.add_argument("--max-skills", type=int, default=10)
    explain_load_parser.add_argument(
        "--inclusion-level", choices=[item.value for item in InclusionLevel], default="summary"
    )
    explain_load_parser.add_argument(
        "--include-non-active",
        action="store_true",
        help="Also consider non-active skills (otherwise only active skills are eligible)",
    )
    explain_load_parser.add_argument(
        "--snippet", action="store_true", help="Include the compiled prompt snippet in the output"
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

    cleanup_parser = subparsers.add_parser(
        "cleanup-skills",
        parents=[dry_run_parent],
        help="Report (and optionally apply) cleanup for stale, noisy, and overlapping skills",
    )
    cleanup_parser.add_argument("--registry-root")
    cleanup_parser.add_argument(
        "--now", help="ISO 8601 timestamp to evaluate expiry against (default: current time)"
    )
    cleanup_parser.add_argument(
        "--write",
        action="store_true",
        help="Apply the safe automated subset (deprecate expired skills through the lifecycle)",
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

    if args.command == "cluster":
        detector = LessonDetector()
        sanitizer = TraceSanitizer() if args.sanitize else None
        candidates = []
        for trace_path in args.trace_paths:
            bundle = load_trace_bundle(trace_path)
            if sanitizer is not None:
                bundle = sanitizer.sanitize(bundle)
            candidates.extend(detector.detect(bundle))
        clusters = LessonClusterer(threshold=args.threshold).cluster(candidates)
        _print_json([cluster.to_dict() for cluster in clusters])
        return 0

    if args.command == "eval-detection":
        corpus = DetectionCorpus.from_file(args.corpus_path)
        report = run_detection_eval(corpus)
        _print_json(report.to_dict())
        if args.min_precision is not None and report.precision < args.min_precision:
            print(
                f"Error: detection precision {report.precision:.3f} is below the required "
                f"minimum {args.min_precision:.3f}",
                file=sys.stderr,
            )
            return 1
        if args.min_recall is not None and report.recall < args.min_recall:
            print(
                f"Error: detection recall {report.recall:.3f} is below the required "
                f"minimum {args.min_recall:.3f}",
                file=sys.stderr,
            )
            return 1
        return 0

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
        approve_result, missing = _do_approve(
            candidate,
            registry,
            approved_by=args.approved_by,
            name=args.name,
            lesson_id=args.lesson_id,
            skill_id=args.skill_id,
            allow_incomplete=args.allow_incomplete_review,
            dry_run=args.dry_run,
        )
        if approve_result is None:
            print(
                f"Error: cannot approve '{candidate.id}': review is incomplete; unanswered "
                f"required questions: {', '.join(missing)}. Answer them with `lessonweaver "
                f"answer`, or pass --allow-incomplete-review to override.",
                file=sys.stderr,
            )
            return 1
        _print_json(approve_result)
        return 0

    if args.command == "review-trace":
        bundle = load_trace_bundle(args.trace_path)
        if args.sanitize:
            bundle = TraceSanitizer().sanitize(bundle)
        candidates = LessonDetector().detect(bundle)
        registry = _registry(args.registry_root)

        # Parse/validate inputs before persisting anything so a malformed
        # --answer/--free-text fails without leaving partial side effects.
        answers = _parse_kv(args.answer)
        free_text = _parse_kv(args.free_text)

        needs_focus = bool(answers) or args.approve
        focus: LessonCandidate | None = None
        if needs_focus:
            if args.candidate is not None:
                focus = next((c for c in candidates if c.id == args.candidate), None)
                if focus is None:
                    print(
                        f"Error: candidate '{args.candidate}' was not detected in this trace",
                        file=sys.stderr,
                    )
                    return 1
            elif len(candidates) == 1:
                focus = candidates[0]
            else:
                print(
                    f"Error: trace produced {len(candidates)} candidates; pass --candidate "
                    f"to choose which one to answer or approve",
                    file=sys.stderr,
                )
                return 1

        # Apply answers in memory first: _apply_answers raises on an unknown
        # question id, so it runs before any registry write — a bad question id
        # fails without persisting candidates, matching the malformed-flag case.
        if focus is not None and answers:
            focus = _apply_answers(focus, answers, free_text)
            candidates = [focus if c.id == focus.id else c for c in candidates]

        if not args.dry_run:
            for candidate in candidates:
                registry.save_candidate(candidate)

        approval: dict[str, str] | None = None
        if focus is not None:
            if args.approve:
                approval, missing = _do_approve(
                    focus,
                    registry,
                    approved_by=args.approved_by,
                    allow_incomplete=args.allow_incomplete_review,
                    dry_run=args.dry_run,
                )
                if approval is None:
                    print(
                        f"Error: cannot approve '{focus.id}': review is incomplete; unanswered "
                        f"required questions: {', '.join(missing)}. Answer them with --answer, "
                        f"or pass --allow-incomplete-review to override.",
                        file=sys.stderr,
                    )
                    return 1

        reviewed = [focus] if focus is not None else candidates
        packet = {
            "trace_id": bundle.trace_id,
            "candidates": [_review_packet(candidate, args) for candidate in reviewed],
            "approval": approval,
        }
        _print_json(packet)
        return 0

    if args.command == "export-file":
        skill = _load_skill_ref(args.skill, _registry(args.registry_root))
        content = _export_skill(skill, args.format, args.redact, args.applies_to)
        target = Path(args.path)
        existing = target.read_text(encoding="utf-8") if target.exists() else ""
        merged = merge_managed_block(existing, content, skill.id)
        if merged == existing:
            print(f"no changes: {args.path} already has this skill block up to date")
            return 0
        if args.write and not args.dry_run:
            target.write_text(merged, encoding="utf-8")
            print(f"{'updated' if existing else 'created'}: {args.path}")
            return 0
        if args.dry_run:
            print(f"[dry-run] would write to: {args.path}")
        print(diff_managed_file(existing, merged, args.path), end="")
        return 0

    if args.command == "generate-pr-diff":
        candidate = _load_candidate_ref(args.candidate, _registry(args.registry_root))
        try:
            change = plan_coding_agent_change(candidate, args.path)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        if not change.changed:
            print(f"no changes: {args.path} already has this artifact block up to date")
            return 0
        if args.write and not args.dry_run:
            will_create = not change.path.exists()
            apply_file_change(change)
            print(f"{'created' if will_create else 'updated'}: {args.path}")
            return 0
        if args.dry_run:
            print(f"[dry-run] would write to: {args.path}")
        print(change.diff, end="")
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
        query = RetrievalQuery(
            task=args.task,
            agent_type=args.agent_type,
            tools=args.tools,
            scope=args.scope,
            risk_level=args.risk_level,
            max_results=args.max_skills,
        )
        if args.explain:
            diagnostics = explain_load(
                registry.list_skills(),
                query,
                budget_chars=args.budget_chars,
                inclusion_level=InclusionLevel(args.inclusion_level),
                include_snippet=True,
            )
            _print_json(diagnostics.to_dict())
            return 0
        results = SkillRetriever().retrieve(registry.list_skills(), query)
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

    if args.command == "explain-load":
        registry = _registry(args.registry_root)
        query = RetrievalQuery(
            task=args.task,
            agent_type=args.agent_type,
            tools=args.tools,
            scope=args.scope,
            risk_level=args.risk_level,
            max_results=args.max_skills,
            include_non_active=args.include_non_active,
        )
        diagnostics = explain_load(
            registry.list_skills(),
            query,
            budget_chars=args.budget_chars,
            inclusion_level=InclusionLevel(args.inclusion_level),
            include_snippet=args.snippet,
        )
        _print_json(diagnostics.to_dict())
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
        reports = SkillReporter().report_stale(registry, now=_parse_now(args.now))
        _print_json([report.to_dict() for report in reports])
        return 0

    if args.command == "cleanup-skills":
        registry = _registry(args.registry_root)
        moment = _parse_now(args.now)
        cleaner = SkillCleaner()
        actions = cleaner.plan(registry, now=moment)
        applied: list[str] = []
        if args.write and not args.dry_run:
            applied = cleaner.apply(registry, actions, now=moment)
        _print_json({"actions": [action.to_dict() for action in actions], "applied": applied})
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
