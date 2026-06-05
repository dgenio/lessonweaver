"""Drift protection for the sibling interop adapters (#91).

Loads each adapter module from ``examples/interop_adapters/`` by path, maps its
bundled sample, and locks the documented candidate counts so the examples cannot
silently drift.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

from lessonweaver.detection import LessonDetector
from lessonweaver.importers import TraceImporter

ADAPTERS = Path(__file__).resolve().parents[1] / "examples" / "interop_adapters"


def _load_module(filename: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(filename[:-3], ADAPTERS / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sample(filename: str) -> dict:
    return json.loads((ADAPTERS / filename).read_text(encoding="utf-8"))


# (module file, importer class attribute, sample file, expected trace_id, expected candidates)
CASES = [
    (
        "vibeguard_finding.py",
        "VibeguardFindingImporter",
        "sample_vibeguard_finding.json",
        "VG-SECRET-01",
        2,
    ),
    (
        "agent_kernel_actiontrace.py",
        "AgentKernelActionTraceImporter",
        "sample_agent_kernel_actiontrace.json",
        "ak-deploy-001",
        1,
    ),
    (
        "chainweaver_failure.py",
        "ChainWeaverFailureImporter",
        "sample_chainweaver_failure.json",
        "cw-checkout-001",
        # The human-correction recovery plus the new workflow-step-before-failure
        # signal (#55): the flow failed by charging before validating, which is
        # exactly the missing-validation-gate pattern the workflow rule detects.
        2,
    ),
]


@pytest.mark.parametrize(("module_file", "cls_name", "sample_file", "trace_id", "expected"), CASES)
def test_adapter_maps_sample_to_expected_candidates(
    module_file: str, cls_name: str, sample_file: str, trace_id: str, expected: int
) -> None:
    importer = getattr(_load_module(module_file), cls_name)()
    assert isinstance(importer, TraceImporter)

    payload = _sample(sample_file)
    assert importer.can_import(payload) is True

    bundle = importer.import_trace(payload)
    assert bundle.trace_id == trace_id
    assert len(LessonDetector().detect(bundle)) == expected


@pytest.mark.parametrize(("module_file", "cls_name"), [(c[0], c[1]) for c in CASES])
def test_adapter_rejects_foreign_payload(module_file: str, cls_name: str) -> None:
    importer = getattr(_load_module(module_file), cls_name)()
    assert importer.can_import({"totally": "unrelated"}) is False
