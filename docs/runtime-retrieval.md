# Runtime retrieval

`RuntimeLessonRetriever` is the library-level contract for loading applicable
reviewed lessons before an agent run. It returns ranked `SkillCard` retrieval
results without compiling them into a prompt, so adapters can choose their own
rendering and injection path.

```python
from lessonweaver import FileSystemRegistry, RuntimeLessonQuery, RuntimeLessonRetriever

registry = FileSystemRegistry()
results = RuntimeLessonRetriever(registry).retrieve(
    RuntimeLessonQuery(
        task="Review this pull request",
        runtime="coding-agent",
        tools=["github"],
        scope="project",
        risk_level="medium",
    )
)
```

The default contract:

- includes approved and active skills;
- excludes draft, rejected, and deprecated skills;
- respects scope and risk ceilings;
- excludes lessons whose `does_not_apply_when` text matches the query context;
- currently returns skill artifacts only.

Use `SkillLoader` when you want a compiled prompt snippet. Use
`RuntimeLessonRetriever` when a runtime adapter needs the underlying ranked,
governed lessons.
