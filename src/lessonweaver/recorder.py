"""First-party helpers for recording valid lessonweaver traces."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .models import TraceBundle, TraceEvent, TraceEventType
from .sanitization import TraceSanitizer
from .traces import validate_trace_dict


class TraceRecorder:
    """Synchronous recorder for building valid lessonweaver traces in Python agents."""

    def __init__(
        self,
        trace_id: str,
        source: str,
        task: str,
        *,
        sanitize: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.trace_id = trace_id
        self.source = source
        self.task = task
        self.sanitize = sanitize
        self.metadata = dict(metadata or {})
        self.outcome = "unknown"
        self._events: list[TraceEvent] = []

    def _next_id(self) -> str:
        return f"e{len(self._events) + 1}"

    def event(
        self,
        event_type: TraceEventType | str,
        content: str | None = None,
        *,
        status: str | None = None,
        success: bool | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TraceEvent:
        normalized_type = (
            event_type if isinstance(event_type, TraceEventType) else TraceEventType(event_type)
        )
        event = TraceEvent(
            id=self._next_id(),
            type=normalized_type,
            content=content,
            status=status,
            success=success,
            metadata=dict(metadata or {}),
        )
        self._events.append(event)
        return event

    def user_message(self, content: str, *, metadata: dict[str, Any] | None = None) -> TraceEvent:
        return self.event(TraceEventType.USER_MESSAGE, content, metadata=metadata)

    def agent_message(self, content: str, *, metadata: dict[str, Any] | None = None) -> TraceEvent:
        return self.event(TraceEventType.ASSISTANT_MESSAGE, content, metadata=metadata)

    def assistant_message(
        self, content: str, *, metadata: dict[str, Any] | None = None
    ) -> TraceEvent:
        return self.agent_message(content, metadata=metadata)

    def model_call(self, model: str, *, metadata: dict[str, Any] | None = None) -> TraceEvent:
        event_metadata = dict(metadata or {})
        event_metadata.setdefault("model", model)
        return self.event(
            TraceEventType.MODEL_CALL, f"model call: {model}", metadata=event_metadata
        )

    def tool_call(self, tool_name: str, *, metadata: dict[str, Any] | None = None) -> TraceEvent:
        event_metadata = dict(metadata or {})
        event_metadata.setdefault("tool_name", tool_name)
        return self.event(
            TraceEventType.TOOL_CALL,
            f"tool call: {tool_name}",
            metadata=event_metadata,
        )

    def tool_result(
        self,
        tool_name: str,
        *,
        success: bool | None = None,
        content: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TraceEvent:
        event_metadata = dict(metadata or {})
        event_metadata.setdefault("tool_name", tool_name)
        return self.event(
            TraceEventType.TOOL_RESULT,
            content or f"tool result: {tool_name}",
            success=success,
            status="success" if success is True else "failed" if success is False else None,
            metadata=event_metadata,
        )

    def human_correction(
        self, content: str, *, metadata: dict[str, Any] | None = None
    ) -> TraceEvent:
        return self.event(TraceEventType.HUMAN_CORRECTION, content, metadata=metadata)

    def evaluation_result(
        self,
        content: str,
        *,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> TraceEvent:
        return self.event(
            TraceEventType.EVALUATION_RESULT, content, status=status, metadata=metadata
        )

    def workflow_step(self, content: str, *, metadata: dict[str, Any] | None = None) -> TraceEvent:
        return self.event(TraceEventType.WORKFLOW_STEP, content, metadata=metadata)

    def retry(self, content: str, *, metadata: dict[str, Any] | None = None) -> TraceEvent:
        return self.event(TraceEventType.RETRY, content, metadata=metadata)

    def error(
        self,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> TraceEvent:
        return self.event(
            TraceEventType.ERROR,
            content,
            status="error",
            success=False,
            metadata=metadata,
        )

    def final_answer(self, content: str, *, metadata: dict[str, Any] | None = None) -> TraceEvent:
        return self.event(TraceEventType.FINAL_ANSWER, content, metadata=metadata)

    def set_outcome(self, outcome: str) -> None:
        self.outcome = outcome

    def to_bundle(self) -> TraceBundle:
        bundle = TraceBundle(
            trace_id=self.trace_id,
            source=self.source,
            task=self.task,
            events=list(self._events),
            outcome=self.outcome,
            metadata=dict(self.metadata),
        )
        if self.sanitize:
            bundle = TraceSanitizer().sanitize(bundle)
        errors = validate_trace_dict(bundle.to_dict())
        if errors:
            message = "\n".join(f"- {error}" for error in errors)
            raise ValueError(f"Invalid recorded trace:\n{message}")
        return bundle

    def save(self, path: str | Path) -> TraceBundle:
        bundle = self.to_bundle()
        payload = json.dumps(bundle.to_dict(), indent=2, sort_keys=True)
        Path(path).write_text(payload + "\n", encoding="utf-8")
        return bundle


@contextmanager
def record(
    source: str,
    task: str,
    *,
    trace_id: str | None = None,
    output: str | Path | None = None,
    sanitize: bool = False,
    metadata: dict[str, Any] | None = None,
) -> Iterator[TraceRecorder]:
    """Context manager that finalizes a trace, including unhandled exceptions."""
    recorder = TraceRecorder(
        trace_id or f"trace-{uuid.uuid4().hex}",
        source,
        task,
        sanitize=sanitize,
        metadata=metadata,
    )
    try:
        yield recorder
    except Exception as exc:
        recorder.error(f"{type(exc).__name__}: {exc}")
        recorder.set_outcome("failure")
        if output is not None:
            recorder.save(output)
        raise
    else:
        if output is not None:
            recorder.save(output)
