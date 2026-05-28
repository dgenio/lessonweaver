"""Load lessonweaver skills before an OpenAI Agents SDK run.

The lessonweaver portion always runs. The OpenAI Agents SDK is optional: if it
is not installed, the example prints the loaded skill context and explains how it
would be injected into agent instructions, without importing the SDK. No API key
is required to understand the example.

Run it from the repository root:

    python examples/openai_agents_runtime_loader/example.py
"""

from __future__ import annotations

from pathlib import Path

from lessonweaver import FileSystemRegistry, SkillLoader

EXAMPLE_DIR = Path(__file__).resolve().parent
REGISTRY_ROOT = EXAMPLE_DIR / "example_registry"


def load_context_snippet() -> str:
    """Load reviewed skills relevant to the task into a prompt snippet."""
    loader = SkillLoader(registry=FileSystemRegistry(root=REGISTRY_ROOT))
    context = loader.load_for_task(
        task="Review this pull request for missing tests",
        agent_type="coding",
        tools=["github"],
        budget_chars=1500,
    )
    return context.snippet


def main() -> None:
    snippet = load_context_snippet()
    print("=== Loaded skill context ===")
    print(snippet or "(no skills matched the task)")

    instructions = (
        "You are a coding assistant that reviews pull requests.\n\n"
        f"{snippet}\n\n"
        "Apply the operational guidance above before drawing review conclusions."
    )

    try:
        # The OpenAI Agents SDK is optional; importing it here keeps it soft.
        from agents import Agent  # noqa: F401
    except ImportError:
        print("\nThe OpenAI Agents SDK is not installed. Run: pip install openai-agents")
        print("The lessonweaver skill loading above works without the SDK.")
        return

    print("\n=== OpenAI Agents SDK available ===")
    print("Pass instructions into your agent, e.g. Agent(name=..., instructions=instructions).")
    print("Instructions prefix (first 200 chars):")
    print(instructions[:200])


if __name__ == "__main__":
    main()
