import json

from lessonweaver.filemerge import merge_managed_block
from lessonweaver.github_action import main
from lessonweaver.models import RiskLevel, Scope, SkillCard, SkillStatus


def _skill(skill_id: str = "skill-1") -> SkillCard:
    return SkillCard(
        id=skill_id,
        name="PR Diff First",
        description="Inspect changed files before reviewing pull requests.",
        applies_when=["reviewing pull requests"],
        does_not_apply_when=["no code changes"],
        instructions=["Inspect changed files first"],
        anti_patterns=["title-only approval"],
        evidence_trace_ids=["trace-1"],
        confidence=0.8,
        risk_level=RiskLevel.LOW,
        scope=Scope.PROJECT,
        version="0.2.0",
        status=SkillStatus.ACTIVE,
    )


def _write_skill(path, skill: SkillCard) -> None:
    path.write_text(json.dumps(skill.to_dict()), encoding="utf-8")


def test_github_action_lints_skill_directory(capsys, tmp_path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    bad = _skill()
    bad.instructions = []
    _write_skill(skills_dir / "skill.json", bad)

    exit_code = main(["--skills-dir", str(skills_dir)])

    assert exit_code == 1
    out = capsys.readouterr().out
    assert "Skill lint: FAIL" in out
    assert "LW003" in out


def test_github_action_fails_validation_suite(capsys, tmp_path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    _write_skill(skills_dir / "skill.json", _skill())
    suite = {
        "suite_id": "suite-1",
        "skill_id": "skill-1",
        "examples": [
            {"example_id": "fn", "task": "Summarize meeting notes", "should_load": True},
        ],
    }
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(json.dumps(suite), encoding="utf-8")

    exit_code = main(["--skills-dir", str(skills_dir), "--validation-suites", str(suite_path)])

    assert exit_code == 1
    assert f"{suite_path}: 0 passed, 1 failed" in capsys.readouterr().out


def test_github_action_fails_on_managed_block_drift(capsys, tmp_path) -> None:
    skill = _skill()
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    _write_skill(skills_dir / "skill.json", skill)
    target = tmp_path / "AGENTS.md"
    target.write_text(
        merge_managed_block("", "- Stale instruction", skill.id),
        encoding="utf-8",
    )

    exit_code = main(["--skills-dir", str(skills_dir), "--instruction-files", str(target)])

    assert exit_code == 1
    out = capsys.readouterr().out
    assert "managed block drift for skill-1" in out
    assert "- Stale instruction" in out
    assert "Inspect changed files first" in out


def test_github_action_writes_step_summary(tmp_path, monkeypatch) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    _write_skill(skills_dir / "skill.json", _skill())
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))

    exit_code = main(["--skills-dir", str(skills_dir)])

    assert exit_code == 0
    content = summary.read_text(encoding="utf-8")
    assert "# lessonweaver governance" in content
    assert "| Skill lint | passed |" in content
