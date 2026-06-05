"""Close the loop: load a reviewed skill card back into an agent's context.

This is the output side of lessonweaver's closed loop. A coding-agent failure
(`traces/agent_merged_without_tests.json`) was detected, reviewed, approved, and
exported as a skill card (`example_registry/skills/skill-run-tests-before-merge.json`
— exactly what `export-skill --format json` emits). Here that card is loaded back
into the context an agent sees *before* its next run, so it starts already knowing
not to repeat the mistake.

The lessonweaver portion always runs. contextweaver is optional: if it is not
installed, the example prints the loaded skill context and explains how
contextweaver would ingest the same skill card, without importing it. The skill
card JSON is the shared interchange format between lessonweaver's export and
contextweaver's skill-card loader (see contextweaver's
``docs/interop_skill_cards.md``).

Run it from the repository root:

    python examples/closed_loop_contextweaver/example.py
"""

from __future__ import annotations

from pathlib import Path

from lessonweaver import FileSystemRegistry, SkillLoader

EXAMPLE_DIR = Path(__file__).resolve().parent
REGISTRY_ROOT = EXAMPLE_DIR / "example_registry"


def load_context_snippet() -> str:
    """Load reviewed skills relevant to the next task into a prompt snippet."""
    loader = SkillLoader(registry=FileSystemRegistry(root=REGISTRY_ROOT))
    context = loader.load_for_task(
        task="Review and merge a pull request",
        agent_type="coding",
        tools=["github"],
        budget_chars=1500,
    )
    return context.snippet


def main() -> None:
    snippet = load_context_snippet()
    print("=== Loaded skill context (what the agent now starts with) ===")
    print(snippet or "(no skills matched the task)")

    try:
        # contextweaver is optional; importing it here keeps the dependency soft.
        import contextweaver  # noqa: F401
    except ImportError:
        print("\ncontextweaver is not installed. Run: pip install contextweaver")
        print(
            "The skill card under example_registry/skills/ is the shared interchange "
            "format; contextweaver ingests that same JSON via its skill-card loader "
            "(see contextweaver's docs/interop_skill_cards.md)."
        )
        return

    print("\n=== contextweaver available ===")
    print(
        "Load the skill card under example_registry/skills/ with contextweaver's "
        "skill-card loader to inject this guidance into the agent's context before "
        "its next run. See contextweaver's docs/interop_skill_cards.md."
    )


if __name__ == "__main__":
    main()
