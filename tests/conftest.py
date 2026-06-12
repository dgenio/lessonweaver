from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="Rewrite checked-in golden output files for exporter snapshot tests.",
    )


if os.name == "nt":

    @pytest.fixture
    def tmp_path(request: pytest.FixtureRequest) -> Path:
        """Repo-local tmp_path fallback for Windows environments with locked temp dirs."""
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", request.node.nodeid)
        root = Path(".test_tmp") / safe_name
        if root.exists():
            shutil.rmtree(root, ignore_errors=True)
        root.mkdir(parents=True, exist_ok=True)
        try:
            yield root
        finally:
            shutil.rmtree(root, ignore_errors=True)
