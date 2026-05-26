"""Trace schema helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import TraceBundle, TraceEventType


def validate_trace_dict(data: dict[str, Any]) -> list[str]:
    """Return human-readable validation errors for a trace payload."""
    errors: list[str] = []
    required_fields = ["trace_id", "source", "task", "events", "outcome"]

    for field in required_fields:
        if field not in data:
            errors.append(f"missing required field: {field}")
            continue
        if data[field] in ("", None, []):
            errors.append(f"field '{field}' must be non-empty")

    events = data.get("events")
    if events is None:
        return errors
    if not isinstance(events, list):
        errors.append("field 'events' must be a list")
        return errors

    seen_ids: set[str] = set()
    valid_event_types = {event_type.value for event_type in TraceEventType}
    for index, event in enumerate(events):
        prefix = f"event[{index}]"
        if not isinstance(event, dict):
            errors.append(f"{prefix}: must be an object")
            continue

        event_id = event.get("id")
        if not isinstance(event_id, str) or not event_id.strip():
            errors.append(f"{prefix}: missing non-empty id")
        elif event_id in seen_ids:
            errors.append(f"event '{event_id}': duplicate id")
        else:
            seen_ids.add(event_id)

        event_type = event.get("type")
        if not isinstance(event_type, str) or not event_type.strip():
            errors.append(f"{prefix}: missing non-empty type")
        elif event_type not in valid_event_types:
            errors.append(f"{prefix}: unknown type '{event_type}'")

    return errors


def load_trace_bundle(path: str | Path) -> TraceBundle:
    """Load and validate a trace bundle from a JSON file path."""
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Invalid trace bundle:\n- top-level JSON value must be an object")
    errors = validate_trace_dict(payload)
    if errors:
        message = "\n".join(f"- {error}" for error in errors)
        raise ValueError(f"Invalid trace bundle:\n{message}")
    return TraceBundle.from_dict(payload)
