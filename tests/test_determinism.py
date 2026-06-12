import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "determinism_digest.py"


def _load_digest_module():
    spec = importlib.util.spec_from_file_location("determinism_digest", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_core_pipeline_determinism_digest_is_stable() -> None:
    digest = _load_digest_module()
    document = digest.build_digest_document()

    assert document["trace_count"] == len(list((ROOT / "examples" / "traces").glob("*.json")))
    assert document["normalized_fields"] == [
        "approved_at",
        "created_at",
        "expires_at",
        "updated_at",
    ]
    assert len(document["digest"]) == 64


def test_core_pipeline_determinism_detects_export_timestamps() -> None:
    digest = _load_digest_module()
    original_export_skill = digest._export_skill

    def nondeterministic_export(*args, **kwargs):
        return original_export_skill(*args, **kwargs) + datetime.now(timezone.utc).isoformat()

    digest._export_skill = nondeterministic_export

    with pytest.raises(AssertionError, match="changed between fresh runs"):
        digest.build_digest_document()
