# Governed operational memory

lessonweaver's durable memory is reviewed operational memory, not unrestricted
chat memory. The filesystem registry persists reviewed lessons, generated
skills, exported artifacts, and usage evidence with lifecycle, scope, risk, and
trace provenance.

Use `build_governed_memory_snapshot` to inspect what a registry currently
contains:

```python
from lessonweaver import FileSystemRegistry, build_governed_memory_snapshot

snapshot = build_governed_memory_snapshot(FileSystemRegistry())
print(snapshot.to_dict())
```

The snapshot reports:

- persisted reviewed lessons and skills;
- lifecycle counts such as approved lessons, active skills, and deprecated
  skills;
- evidence trace ids retained across processes;
- governance warnings for missing evidence or deprecated skills;
- an explicit `generic_chat_memory = False` boundary.

This keeps the roadmap focused on governed storage, review status, evidence
retention, privacy/redaction boundaries, stale cleanup, and contradiction
handling instead of storing arbitrary conversational facts.
