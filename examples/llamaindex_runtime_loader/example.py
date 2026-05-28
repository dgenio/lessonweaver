"""Load lessonweaver skills before a LlamaIndex agent run.

The lessonweaver portion always runs. LlamaIndex is optional: if it is not
installed, the example prints the loaded skill context and explains how it would
be injected, without importing LlamaIndex.

Run it from the repository root:

    python examples/llamaindex_runtime_loader/example.py
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
        task="Answer a question about our refund policy",
        agent_type="customer_service",
        budget_chars=1500,
    )
    return context.snippet


def main() -> None:
    snippet = load_context_snippet()
    print("=== Loaded skill context ===")
    print(snippet or "(no skills matched the task)")

    system_prompt = (
        "You are a helpful customer service assistant.\n\n"
        f"{snippet}\n\n"
        "Answer the user's question using the operational guidance above."
    )

    try:
        # LlamaIndex is optional; importing it here keeps the dependency soft.
        from llama_index.core.agent import ReActAgent  # noqa: F401
    except ImportError:
        print("\nLlamaIndex is not installed. Run: pip install llama-index")
        print("The lessonweaver skill loading above works without LlamaIndex.")
        return

    print("\n=== LlamaIndex available ===")
    print("Pass system_prompt into your agent, e.g. ReActAgent.from_tools(...).")
    print("System prompt prefix (first 200 chars):")
    print(system_prompt[:200])


if __name__ == "__main__":
    main()
