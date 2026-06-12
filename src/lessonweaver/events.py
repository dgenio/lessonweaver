"""Synchronous lifecycle events for lessonweaver operations."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class LifecycleEventType(str, Enum):
    TRACE_LOADED = "trace_loaded"
    CANDIDATE_DETECTED = "candidate_detected"
    CANDIDATE_REJECTED = "candidate_rejected"
    REVIEW_QUESTION_GENERATED = "review_question_generated"
    REVIEW_ANSWER_APPLIED = "review_answer_applied"
    SKILL_EXPORTED = "skill_exported"
    SKILL_RETRIEVED = "skill_retrieved"
    SKILL_OMITTED_BUDGET = "skill_omitted_budget"
    VALIDATION_PASSED = "validation_passed"
    VALIDATION_FAILED = "validation_failed"


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class LifecycleEvent:
    event_type: LifecycleEventType
    subject_id: str
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=_utc_timestamp)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "subject_id": self.subject_id,
            "metadata": dict(self.metadata),
        }


EventListener = Callable[[LifecycleEvent], None]


class EventEmitter:
    """Small synchronous emitter with listener registration and scoped capture."""

    def __init__(self) -> None:
        self._listeners: list[EventListener] = []

    def on(self, listener: EventListener) -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)

    def off(self, listener: EventListener) -> None:
        self._listeners = [registered for registered in self._listeners if registered != listener]

    def emit(self, event: LifecycleEvent) -> None:
        for listener in tuple(self._listeners):
            listener(event)

    @contextmanager
    def capture(self) -> Iterator[list[LifecycleEvent]]:
        events: list[LifecycleEvent] = []
        self.on(events.append)
        try:
            yield events
        finally:
            self.off(events.append)


emitter = EventEmitter()
