"""Import-graph guardrails for the deterministic core."""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path


def test_public_package_import_loads_no_third_party_modules() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = textwrap.dedent(
        f"""
        import json
        import sys

        sys.path.insert(0, {str(repo_root / "src")!r})
        before = set(sys.modules)
        import lessonweaver  # noqa: F401

        allowed = set(sys.stdlib_module_names) | {{"lessonweaver"}}
        loaded = set(sys.modules) - before
        unexpected = sorted(
            top_level
            for top_level in {{name.split(".", 1)[0] for name in loaded}}
            if top_level not in allowed and not top_level.startswith("_")
        )
        print(json.dumps(unexpected))
        """
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout) == []
