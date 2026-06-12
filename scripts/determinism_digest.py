"""Generate a deterministic digest for the core detect -> review -> export loop."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from lessonweaver.cli import _apply_answers, _do_approve, _export_skill
from lessonweaver.detection import LessonDetector
from lessonweaver.interview import LessonInterviewer
from lessonweaver.models import RecommendedActionType, RiskLevel
from lessonweaver.registry import FileSystemRegistry
from lessonweaver.traces import load_trace_bundle

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRACE_DIR = ROOT / "examples" / "traces"
EXPORT_FORMATS = [
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
]
NORMALIZED_FIELDS = ["approved_at", "created_at", "expires_at", "updated_at"]
_NORMALIZED_FIELD_SET = set(NORMALIZED_FIELDS)


def _canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (
                "<timestamp>"
                if key in _NORMALIZED_FIELD_SET and item is not None
                else _canonicalize(item)
            )
            for key, item in sorted(value.items())
        }
    if isinstance(value, list):
        return [_canonicalize(item) for item in value]
    return value


def _canonical_export(content: str) -> Any:
    stripped = content.strip()
    if stripped.startswith(("{", "[")):
        try:
            return _canonicalize(json.loads(stripped))
        except json.JSONDecodeError:
            pass
    return content


def _review_answers(candidate) -> dict[str, str]:
    answers = {
        "scope": candidate.scope.value,
        "action_type": candidate.recommended_action_type.value,
        "risk_level": candidate.risk_level.value,
        "applicability": "high_risk",
        "negative_conditions": "different_domain",
        "decision": "approve",
    }
    if candidate.risk_level is RiskLevel.HIGH:
        answers["approval_requirement"] = "explicit_approval"
    if candidate.recommended_action_type is RecommendedActionType.WORKFLOW_CHANGE:
        answers["workflow_determinism"] = "deterministic_rule"
    return answers


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def build_payload(trace_paths: list[Path]) -> dict[str, Any]:
    detector = LessonDetector()
    interviewer = LessonInterviewer()
    traces: list[dict[str, Any]] = []

    with TemporaryDirectory() as registry_root:
        registry = FileSystemRegistry(registry_root)
        for trace_path in trace_paths:
            bundle = load_trace_bundle(trace_path)
            trace_entry: dict[str, Any] = {
                "path": _relative(trace_path),
                "candidates": [],
            }
            for candidate in detector.detect(bundle):
                initial_questions = [
                    question.to_dict() for question in interviewer.next_questions(candidate, [])
                ]
                reviewed = _apply_answers(candidate, _review_answers(candidate), {})
                approval, missing = _do_approve(
                    reviewed,
                    registry,
                    approved_by="determinism-suite",
                    allow_incomplete=False,
                )
                if approval is None:
                    raise RuntimeError(
                        f"review answers left {candidate.id} incomplete: {', '.join(missing)}"
                    )
                skill = registry.load_skill(approval["skill_id"])
                trace_entry["candidates"].append(
                    {
                        "candidate": _canonicalize(candidate.to_dict()),
                        "initial_questions": _canonicalize(initial_questions),
                        "reviewed_candidate": _canonicalize(reviewed.to_dict()),
                        "approval": _canonicalize(approval),
                        "exports": {
                            fmt: _canonical_export(
                                _export_skill(skill, fmt, redact=True, applies_to="**")
                            )
                            for fmt in EXPORT_FORMATS
                        },
                    }
                )
            traces.append(trace_entry)

    return {
        "export_formats": EXPORT_FORMATS,
        "normalized_fields": NORMALIZED_FIELDS,
        "traces": traces,
    }


def digest_payload(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def trace_paths(trace_dir: Path = DEFAULT_TRACE_DIR) -> list[Path]:
    return sorted(trace_dir.glob("*.json"))


def build_digest_document(trace_dir: Path = DEFAULT_TRACE_DIR) -> dict[str, Any]:
    paths = trace_paths(trace_dir)
    first = build_payload(paths)
    second = build_payload(paths)
    if first != second:
        raise AssertionError("determinism payload changed between fresh runs")
    return {
        "digest": digest_payload(first),
        "trace_count": len(paths),
        "normalized_fields": NORMALIZED_FIELDS,
        "export_formats": EXPORT_FORMATS,
        "payload": first,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace-dir", type=Path, default=DEFAULT_TRACE_DIR)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    document = build_digest_document(args.trace_dir)
    text = json.dumps(document, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
