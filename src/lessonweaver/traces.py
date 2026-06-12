"""Trace schema helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import TraceBundle, TraceEventType


@dataclass(frozen=True, slots=True)
class TraceValidationIssue:
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


def validate_trace_dict(data: dict[str, Any]) -> list[str]:
    """Return human-readable validation errors for a trace payload."""
    return [str(issue) for issue in validate_trace_issues(data)]


def validate_trace_issues(data: dict[str, Any]) -> list[TraceValidationIssue]:
    """Return structured validation errors for a trace payload."""
    errors: list[TraceValidationIssue] = []
    required_fields = ["trace_id", "source", "task", "events", "outcome"]

    for field in required_fields:
        if field not in data:
            errors.append(TraceValidationIssue(f"/{field}", f"missing required field: {field}"))
            continue
        if data[field] in ("", None, []):
            errors.append(TraceValidationIssue(f"/{field}", f"field '{field}' must be non-empty"))

    events = data.get("events")
    if events is None:
        return errors
    if not isinstance(events, list):
        errors.append(TraceValidationIssue("/events", "field 'events' must be a list"))
        return errors

    seen_ids: set[str] = set()
    valid_event_types = {event_type.value for event_type in TraceEventType}
    for index, event in enumerate(events):
        prefix = f"/events/{index}"
        if not isinstance(event, dict):
            errors.append(TraceValidationIssue(prefix, "must be an object"))
            continue

        event_id = event.get("id")
        if not isinstance(event_id, str) or not event_id.strip():
            errors.append(TraceValidationIssue(f"{prefix}/id", "missing non-empty id"))
        elif event_id in seen_ids:
            errors.append(TraceValidationIssue(f"{prefix}/id", f"event '{event_id}': duplicate id"))
        else:
            seen_ids.add(event_id)

        event_type = event.get("type")
        if not isinstance(event_type, str) or not event_type.strip():
            errors.append(TraceValidationIssue(f"{prefix}/type", "missing non-empty type"))
        elif event_type not in valid_event_types:
            errors.append(TraceValidationIssue(f"{prefix}/type", f"unknown type '{event_type}'"))

    return errors


def load_trace_bundle(path: str | Path) -> TraceBundle:
    """Load and validate a trace bundle from a JSON file path.

    Delegates the validate-and-build step to :class:`DictTraceImporter`, making
    the canonical loader a thin wrapper over the :class:`TraceImporter` protocol
    (issue #52). The import is function-local to avoid a module import cycle, as
    ``importers`` reuses :func:`validate_trace_dict` from this module.
    """
    from .importers import DictTraceImporter

    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Invalid trace bundle:\n- top-level JSON value must be an object")
    return DictTraceImporter().import_trace(payload)
