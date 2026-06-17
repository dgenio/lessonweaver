"""GitHub Action governance runner for lessonweaver repositories."""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .export import (
    export_agents_md_fragment,
    export_claude_md_snippet,
    export_copilot_repo_instruction,
)
from .filemerge import diff_managed_file, merge_managed_block
from .lint import LintSeverity, SkillLinter
from .models import SkillCard
from .registry import FileSystemRegistry
from .validation import ValidationSuite, run_validation_suite

_MANAGED_BEGIN_RE = re.compile(r"<!-- lessonweaver:begin skill_id=([^ ]+) -->")


@dataclass(slots=True)
class GateResult:
    title: str
    passed: bool
    details: list[str]


def _split_patterns(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[\n,]+", value) if item.strip()]


def _expand_patterns(value: str) -> list[Path]:
    paths: list[Path] = []
    for pattern in _split_patterns(value):
        matches = [Path(match) for match in glob.glob(pattern, recursive=True)]
        if matches:
            paths.extend(matches)
        else:
            paths.append(Path(pattern))
    return sorted({path for path in paths})


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _load_skills_from_dir(skills_dir: str) -> tuple[list[SkillCard], dict[str, SkillCard]]:
    root = Path(skills_dir)
    skills: list[SkillCard] = []
    for path in sorted(root.rglob("*.json")):
        data = _read_json(path)
        if "name" not in data:
            continue
        skills.append(SkillCard.from_dict(data))
    return skills, {skill.id: skill for skill in skills}


def _skill_lookup(
    *,
    skills_by_id: dict[str, SkillCard],
    registry_root: str | None,
    skill_id: str,
) -> SkillCard:
    if skill_id in skills_by_id:
        return skills_by_id[skill_id]
    if registry_root:
        return FileSystemRegistry(registry_root).load_skill(skill_id)
    raise ValueError(f"skill '{skill_id}' was not found in --skills-dir or --registry-root")


def _export_for_path(skill: SkillCard, path: Path) -> str:
    name = path.name.lower()
    if name == "claude.md":
        return export_claude_md_snippet(skill)
    if name == "copilot-instructions.md":
        return export_copilot_repo_instruction(skill)
    return export_agents_md_fragment(skill)


def lint_skills(skills: list[SkillCard]) -> GateResult:
    details: list[str] = []
    failed = False
    for skill in skills:
        findings = SkillLinter().lint(skill)
        if not findings:
            details.append(f"{skill.id}: ok")
        for finding in findings:
            details.append(
                f"{skill.id}: [{finding.severity.value.upper()}] "
                f"{finding.rule_id}: {finding.message}"
            )
        if any(finding.severity is LintSeverity.ERROR for finding in findings):
            failed = True
    if not skills:
        details.append("No skill JSON files found.")
    return GateResult("Skill lint", not failed, details)


def validate_suites(suite_paths: Iterable[Path], skills: list[SkillCard]) -> GateResult:
    details: list[str] = []
    failed = False
    for path in suite_paths:
        suite = ValidationSuite.from_dict(_read_json(path))
        result = run_validation_suite(suite, skills)
        details.append(
            f"{path}: {result.passed} passed, {result.failed} failed "
            f"(pass rate {result.pass_rate:.2f})"
        )
        if result.failed:
            failed = True
    if not details:
        details.append("No validation suites configured.")
    return GateResult("Validation suites", not failed, details)


def check_instruction_drift(
    instruction_paths: Iterable[Path],
    *,
    skills_by_id: dict[str, SkillCard],
    registry_root: str | None,
) -> GateResult:
    details: list[str] = []
    failed = False
    for path in instruction_paths:
        if not path.exists():
            details.append(f"{path}: missing; skipped")
            continue
        existing = path.read_text(encoding="utf-8")
        skill_ids = sorted(set(_MANAGED_BEGIN_RE.findall(existing)))
        if not skill_ids:
            details.append(f"{path}: no lessonweaver managed blocks")
            continue
        for skill_id in skill_ids:
            skill = _skill_lookup(
                skills_by_id=skills_by_id,
                registry_root=registry_root,
                skill_id=skill_id,
            )
            merged = merge_managed_block(existing, _export_for_path(skill, path), skill.id)
            diff = diff_managed_file(existing, merged, str(path))
            if diff:
                failed = True
                details.append(f"{path}: managed block drift for {skill.id}\n{diff}")
            else:
                details.append(f"{path}: {skill.id} up to date")
    if not details:
        details.append("No instruction files configured.")
    return GateResult("Instruction drift", not failed, details)


def _write_summary(results: list[GateResult]) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    lines = ["# lessonweaver governance", "", "| Gate | Result |", "| --- | --- |"]
    for result in results:
        outcome = "passed" if result.passed else "failed"
        lines.append(f"| {result.title} | {outcome} |")
    lines.append("")
    for result in results:
        lines.extend([f"## {result.title}", ""])
        for detail in result.details:
            lines.append(f"- {detail}")
        lines.append("")
    Path(summary_path).write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry-root")
    parser.add_argument("--skills-dir", default="")
    parser.add_argument("--validation-suites", default="")
    parser.add_argument("--instruction-files", default="")
    args = parser.parse_args(argv)

    skills: list[SkillCard] = []
    skills_by_id: dict[str, SkillCard] = {}
    if args.skills_dir:
        skills, skills_by_id = _load_skills_from_dir(args.skills_dir)
    elif args.registry_root:
        skills = FileSystemRegistry(args.registry_root).list_skills()
        skills_by_id = {skill.id: skill for skill in skills}

    results = [
        lint_skills(skills),
        validate_suites(_expand_patterns(args.validation_suites), skills),
        check_instruction_drift(
            _expand_patterns(args.instruction_files),
            skills_by_id=skills_by_id,
            registry_root=args.registry_root,
        ),
    ]

    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"== {result.title}: {status} ==")
        for detail in result.details:
            print(detail)

    _write_summary(results)
    return 1 if any(not result.passed for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
