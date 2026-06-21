"""Registries for reviewed lessons and generated skills."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeVar

from .models import (
    ExportArtifact,
    LessonCandidate,
    OperationalLesson,
    SkillCard,
    SkillUsageEvent,
)

T = TypeVar("T")
_REGISTRY_ENV_VAR = "LESSONWEAVER_REGISTRY"


def resolve_registry_root(explicit: str | Path | None = None) -> Path:
    """Resolve the registry root using flag, env, project-local, then home default."""
    if explicit is not None:
        return Path(explicit).expanduser()

    env_root = os.environ.get(_REGISTRY_ENV_VAR)
    if env_root:
        return Path(env_root).expanduser()

    for directory in (Path.cwd(), *Path.cwd().parents):
        project_registry = directory / ".lessonweaver" / "registry"
        if project_registry.is_dir():
            return project_registry

    return Path.home() / ".lessonweaver" / "registry"


@dataclass(slots=True)
class LessonRegistry:
    lessons: dict[str, LessonCandidate] = field(default_factory=dict)
    skills: dict[str, SkillCard] = field(default_factory=dict)

    def add_lesson(self, candidate: LessonCandidate) -> None:
        self.lessons[candidate.id] = candidate

    def add_skill(self, skill: SkillCard) -> None:
        self.skills[skill.id] = skill

    def get_lesson(self, lesson_id: str) -> LessonCandidate | None:
        return self.lessons.get(lesson_id)

    def get_skill(self, skill_id: str) -> SkillCard | None:
        return self.skills.get(skill_id)


class FileSystemRegistry:
    """Filesystem-backed JSON registry for lessonweaver objects."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = resolve_registry_root(root)
        self.candidates_dir = self.root / "candidates"
        self.skills_dir = self.root / "skills"
        self.lessons_dir = self.root / "lessons"
        self.artifacts_dir = self.root / "artifacts"
        self.usage_dir = self.root / "usage"

    def save_candidate(self, candidate: LessonCandidate) -> None:
        self._save(self.candidates_dir, candidate.id, candidate.to_dict())

    def load_candidate(self, candidate_id: str) -> LessonCandidate:
        return self._load(self.candidates_dir, candidate_id, LessonCandidate.from_dict, "candidate")

    def list_candidates(self, *, strict: bool = False) -> list[LessonCandidate]:
        return self._list(self.candidates_dir, LessonCandidate.from_dict, strict=strict)

    def delete_candidate(self, candidate_id: str) -> None:
        self._delete(self.candidates_dir, candidate_id, "candidate")

    def save_skill(self, skill: SkillCard) -> None:
        self._save(self.skills_dir, skill.id, skill.to_dict())

    def load_skill(self, skill_id: str) -> SkillCard:
        return self._load(self.skills_dir, skill_id, SkillCard.from_dict, "skill")

    def list_skills(self, *, strict: bool = False) -> list[SkillCard]:
        return self._list(self.skills_dir, SkillCard.from_dict, strict=strict)

    def delete_skill(self, skill_id: str) -> None:
        self._delete(self.skills_dir, skill_id, "skill")

    def save_lesson(self, lesson: OperationalLesson) -> None:
        self._save(self.lessons_dir, lesson.lesson_id, lesson.to_dict())

    def load_lesson(self, lesson_id: str) -> OperationalLesson:
        return self._load(self.lessons_dir, lesson_id, OperationalLesson.from_dict, "lesson")

    def list_lessons(self, *, strict: bool = False) -> list[OperationalLesson]:
        return self._list(self.lessons_dir, OperationalLesson.from_dict, strict=strict)

    def delete_lesson(self, lesson_id: str) -> None:
        self._delete(self.lessons_dir, lesson_id, "lesson")

    def save_artifact(self, artifact: ExportArtifact) -> None:
        self._save(self.artifacts_dir, artifact.artifact_id, artifact.to_dict())

    def load_artifact(self, artifact_id: str) -> ExportArtifact:
        return self._load(self.artifacts_dir, artifact_id, ExportArtifact.from_dict, "artifact")

    def list_artifacts(self, *, strict: bool = False) -> list[ExportArtifact]:
        return self._list(self.artifacts_dir, ExportArtifact.from_dict, strict=strict)

    def delete_artifact(self, artifact_id: str) -> None:
        self._delete(self.artifacts_dir, artifact_id, "artifact")

    def save_usage_event(self, event: SkillUsageEvent) -> None:
        self._save(self.usage_dir, event.id, event.to_dict())

    def load_usage_event(self, event_id: str) -> SkillUsageEvent:
        return self._load(self.usage_dir, event_id, SkillUsageEvent.from_dict, "usage event")

    def list_usage_events(self, *, strict: bool = False) -> list[SkillUsageEvent]:
        return self._list(self.usage_dir, SkillUsageEvent.from_dict, strict=strict)

    def list_skill_usage(self, skill_id: str) -> list[SkillUsageEvent]:
        """Return all recorded usage events for a single skill."""
        return [event for event in self.list_usage_events() if event.skill_id == skill_id]

    def delete_usage_event(self, event_id: str) -> None:
        self._delete(self.usage_dir, event_id, "usage event")

    def _path(self, directory: Path, object_id: str) -> Path:
        _validate_id(object_id)
        return directory / f"{object_id}.json"

    def _save(self, directory: Path, object_id: str, payload: dict[str, object]) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        path = self._path(directory, object_id)
        content = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                dir=directory,
                prefix=f".{object_id}.",
                suffix=".tmp",
                delete=False,
                encoding="utf-8",
            ) as temp_file:
                temp_file.write(content)
                temp_file.flush()
                os.fsync(temp_file.fileno())
                temp_path = Path(temp_file.name)
            os.replace(temp_path, path)
        except Exception:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()
            raise

    def _load(
        self,
        directory: Path,
        object_id: str,
        factory: Callable[[dict[str, object]], T],
        label: str,
    ) -> T:
        path = self._path(directory, object_id)
        if not path.exists():
            raise FileNotFoundError(f"{label} '{object_id}' does not exist in registry")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{label} '{object_id}' registry file contains invalid JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"{label} '{object_id}' registry file must contain a JSON object")
        return factory(payload)

    def _list(
        self,
        directory: Path,
        factory: Callable[[dict[str, object]], T],
        *,
        strict: bool = False,
    ) -> list[T]:
        if not directory.exists():
            return []
        items: list[T] = []
        for path in sorted(directory.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                error = ValueError(f"registry file {path} contains invalid JSON")
                if strict:
                    raise error from exc
                _warn_skipped_registry_file(path, error)
                continue
            if not isinstance(payload, dict):
                error = ValueError(f"registry file {path} must contain a JSON object")
                if strict:
                    raise error
                _warn_skipped_registry_file(path, error)
                continue
            try:
                items.append(factory(payload))
            except (ValueError, KeyError, TypeError) as exc:
                if strict:
                    raise
                _warn_skipped_registry_file(path, exc)
        return items

    def _delete(self, directory: Path, object_id: str, label: str) -> None:
        path = self._path(directory, object_id)
        if not path.exists():
            raise FileNotFoundError(f"{label} '{object_id}' does not exist in registry")
        path.unlink()


def _validate_id(object_id: str) -> None:
    if (
        not object_id
        or "/" in object_id
        or "\\" in object_id
        or ".." in object_id
        or "\x00" in object_id
    ):
        raise ValueError(f"unsafe registry id: {object_id!r}")


def _warn_skipped_registry_file(path: Path, error: Exception) -> None:
    print(f"warning: skipped registry file {path}: {error}", file=sys.stderr)
