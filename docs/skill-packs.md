# Skill Packs

Skill packs are portable JSON bundles for sharing reviewed `SkillCard`s across
registries, repositories, and teams. They preserve provenance and integrity, but
they do not grant activation authority in the destination registry.

## Commands

```bash
# Export reviewed skills from a registry
lessonweaver pack export skill-1 skill-2 --registry-root .lessonweaver \
  --name coding-agent-basics --version 1.0.0 --publisher ai-platform \
  --output coding-agent-basics.pack.json

# Verify contents without importing
lessonweaver pack inspect coding-agent-basics.pack.json

# Import into another registry as experimental skills
lessonweaver pack import coding-agent-basics.pack.json --registry-root .lessonweaver
```

`pack export` redacts obvious sensitive strings by default. Pass
`--no-redact` only for trusted internal transport. Export refuses skills that
are not `approved` or `active` unless `--allow-unapproved` is set.

## Format

Each pack is a single JSON object:

```json
{
  "schema": "lessonweaver/skill-pack@1",
  "metadata": {
    "name": "coding-agent-basics",
    "version": "1.0.0",
    "publisher": "ai-platform",
    "created_at": "2026-06-12T12:00:00+00:00"
  },
  "skills": [
    {
      "skill": {
        "id": "skill-1",
        "status": "approved"
      },
      "digest": "sha256-of-canonical-skill-json"
    }
  ],
  "pack_digest": "sha256-of-canonical-pack-json"
}
```

Digests use SHA-256 over canonical JSON with sorted keys and fixed separators.
`pack inspect` and `pack import` verify the pack-level digest and every skill
digest before trusting the contents.

## Trust Model

Digests detect accidental or malicious byte changes after export. They do not
prove who authored a pack. Treat unsigned packs as provenance-preserving
artifacts, not as endorsements.

Imported skills always arrive with status `experimental`, never `active`, and
record `metadata.source_pack` with the pack name, version, publisher, schema,
and digest. Promote imported skills through the normal local governance flow
after review.

If an imported skill id already exists in the destination registry, import
reports the collision and leaves the existing skill unchanged.
