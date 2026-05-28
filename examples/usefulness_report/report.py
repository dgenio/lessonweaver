"""Report basic usefulness signals for one reviewed skill.

Deterministic, no model calls. For each bundled trace this counts whether the
reviewed skill would have been retrieved (matching) or not (unrelated), and how
many skills were included vs. omitted by the loader. These are coarse signals,
not proof that a skill helped — see the README for the limits.

Run it from the repository root:

    python examples/usefulness_report/report.py
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from lessonweaver import FileSystemRegistry, SkillLoader, load_trace_bundle

EXAMPLE_DIR = Path(__file__).resolve().parent
REGISTRY_ROOT = EXAMPLE_DIR / "registry"
TRACES_DIR = EXAMPLE_DIR / "traces"
SKILL_ID = "skill-refund-policy-version"


@dataclass(slots=True)
class UsefulnessReport:
    matching_traces: int
    unrelated_traces: int
    retrieved_skills: int
    ignored_skills: int
    rows: list[tuple[str, bool]]


def compute_report(
    registry_root: Path = REGISTRY_ROOT,
    traces_dir: Path = TRACES_DIR,
    skill_id: str = SKILL_ID,
) -> UsefulnessReport:
    loader = SkillLoader(registry=FileSystemRegistry(root=registry_root))
    matching = 0
    unrelated = 0
    retrieved = 0
    ignored = 0
    rows: list[tuple[str, bool]] = []
    for path in sorted(traces_dir.glob("*.json")):
        bundle = load_trace_bundle(path)
        context = loader.load_for_task(task=bundle.task)
        loaded = skill_id in context.included_skills
        matching += int(loaded)
        unrelated += int(not loaded)
        retrieved += len(context.included_skills)
        ignored += len(context.omitted_skills)
        rows.append((path.name, loaded))
    return UsefulnessReport(matching, unrelated, retrieved, ignored, rows)


def main() -> None:
    report = compute_report()
    print(f"Skill under review: {SKILL_ID}")
    print(f"Matching traces:    {report.matching_traces}")
    print(f"Unrelated traces:   {report.unrelated_traces}")
    print(f"Retrieved skills:   {report.retrieved_skills}")
    print(f"Ignored skills:     {report.ignored_skills}")
    print("Per trace:")
    for name, loaded in report.rows:
        print(f"  {'retrieved' if loaded else 'ignored  '}  {name}")


if __name__ == "__main__":
    main()
