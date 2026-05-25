"""Trace schema helpers."""

from __future__ import annotations

import json
from pathlib import Path

from .models import TraceBundle


def load_trace_bundle(path: str | Path) -> TraceBundle:
    """Load a trace bundle from a JSON file path."""
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return TraceBundle.from_dict(payload)
