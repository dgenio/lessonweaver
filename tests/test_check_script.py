"""The canonical local check must stay identical to CI (scripts/check.py, #290).

The required sequence used to be written down three times — the workflow,
CONTRIBUTING and the pull-request template — with nothing holding the copies
together. These tests are the thing that holds them together: if a step is
added to, removed from, or reordered in ``ci.yml`` without the same change in
``scripts/check.py``, the suite fails and names the difference.

The scanner below reads the workflow as text rather than as YAML on purpose:
PyYAML is not in the ``dev`` dependency group, and #290 asks for a
dependency-light gate. It is deliberately strict — if the workflow's shape
changes enough to confuse it, that is a prompt to re-read this file, not a
reason to loosen it.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "check.py"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"
CONTRIBUTING_PATH = REPO_ROOT / "CONTRIBUTING.md"
PR_TEMPLATE_PATH = REPO_ROOT / ".github" / "pull_request_template.md"

CANONICAL_COMMAND = "python scripts/check.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_script", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_script = _load_module()


def _job_steps(workflow_text: str, job: str) -> list[tuple[str, list[str]]]:
    """Return ``(step name, command lines)`` for one job's ``run:`` steps."""
    lines = workflow_text.splitlines()
    start = next(
        (i for i, line in enumerate(lines) if line == f"  {job}:"),
        None,
    )
    assert start is not None, f"job {job!r} not found in {WORKFLOW_PATH.name}"
    end = next(
        (
            i
            for i in range(start + 1, len(lines))
            if re.match(r"^  \S", lines[i]) and lines[i].rstrip().endswith(":")
        ),
        len(lines),
    )

    steps: list[tuple[str, list[str]]] = []
    name = ""
    index = start
    while index < end:
        line = lines[index]
        if match := re.match(r"^      - (?:name: )?(.*)$", line):
            name = match.group(1) if line.lstrip().startswith("- name:") else ""
        elif match := re.match(r"^\s+name: (.*)$", line):
            name = match.group(1)
        elif match := re.match(r"^(\s+)run: \|\s*$", line):
            indent = len(match.group(1))
            body: list[str] = []
            index += 1
            while index < end and (
                not lines[index].strip() or len(lines[index]) - len(lines[index].lstrip()) > indent
            ):
                if lines[index].strip():
                    body.append(lines[index].strip())
                index += 1
            steps.append((name, body))
            continue
        elif match := re.match(r"^\s+run: (\S.*)$", line):
            steps.append((name, [match.group(1).strip()]))
        index += 1
    return steps


def _validation_commands() -> list[str]:
    """CI's required checks: every run step in `test` that is not the install."""
    steps = _job_steps(WORKFLOW_PATH.read_text(encoding="utf-8"), "test")
    assert steps, "no run steps parsed from the test job — the scanner is broken"
    assert any("install" in name.lower() for name, _ in steps), (
        "no install step found in the test job; the filter below would be "
        "excluding nothing, so this scanner can no longer be trusted"
    )
    commands: list[str] = []
    for name, body in steps:
        if "install" in name.lower():
            continue
        commands.extend(body)
    return commands


class TestNoDriftFromCI:
    def test_the_script_runs_exactly_cis_checks_in_cis_order(self) -> None:
        declared = [check_script.display(command) for _, _, command in check_script.CHECKS]
        assert declared == _validation_commands(), (
            "scripts/check.py and .github/workflows/ci.yml disagree about the "
            "required checks. Whichever changed, change the other."
        )

    def test_the_benchmark_guard_is_included(self) -> None:
        declared = [check_script.display(command) for _, _, command in check_script.CHECKS]
        assert any("eval-detection" in command for command in declared)

    def test_the_scanner_notices_a_changed_workflow(self) -> None:
        """The check that the check works.

        A drift guard that cannot see drift is worse than none, so feed the
        scanner a workflow with one step altered and require a difference.
        """
        altered = WORKFLOW_PATH.read_text(encoding="utf-8").replace(
            "run: mypy src/lessonweaver/", "run: mypy src/"
        )
        steps = _job_steps(altered, "test")
        commands = [c for name, body in steps if "install" not in name.lower() for c in body]
        declared = [check_script.display(command) for _, _, command in check_script.CHECKS]
        assert declared != commands


class TestDefaultRunChangesNothing:
    def test_the_benchmark_step_compares_and_does_not_write(self) -> None:
        benchmark = next(
            command for _, _, command in check_script.CHECKS if "eval-detection" in command
        )
        assert "--compare-results" in benchmark
        assert ">" not in check_script.display(benchmark)

    def test_no_check_writes_a_generated_artifact(self) -> None:
        for _, _, command in check_script.CHECKS:
            rendered = check_script.display(command)
            assert "--fix" not in rendered, rendered
            assert not re.search(r"\bruff format\b(?!.*--check)", rendered), rendered


class TestToolsComeFromThisInterpreter:
    @pytest.mark.parametrize("tool", ["ruff", "mypy", "pytest"])
    def test_python_tools_run_as_modules(self, tool: str) -> None:
        """CI runs these bare on a clean runner; a developer machine is not one.

        Resolving them from PATH means the gate can report the behaviour of some
        other environment's tool while looking like it reports the code's.
        """
        kinds = {command[0]: kind for _, kind, command in check_script.CHECKS}
        assert kinds[tool] == "module"
        resolved = check_script.resolve("module", (tool,))
        assert resolved[:3] == [sys.executable, "-m", tool]


class TestDocumentationPointsHere:
    @pytest.mark.parametrize("path", [CONTRIBUTING_PATH, PR_TEMPLATE_PATH], ids=lambda p: p.name)
    def test_the_canonical_command_is_documented(self, path: Path) -> None:
        assert CANONICAL_COMMAND in path.read_text(encoding="utf-8"), (
            f"{path.name} does not reference `{CANONICAL_COMMAND}`; it will "
            "drift from the workflow again"
        )

    def test_benchmark_regeneration_is_documented(self) -> None:
        doc = (REPO_ROOT / "docs" / "detection-benchmark.md").read_text(encoding="utf-8")
        assert check_script.BENCHMARK_REGEN in doc, (
            "the regeneration command printed on failure is not the one the documentation gives"
        )


class TestEntryPoint:
    def test_list_prints_every_check_without_running_them(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--list"],
            capture_output=True,
            text=True,
            check=True,
        )
        for name, _, command in check_script.CHECKS:
            assert f"{name}: {check_script.display(command)}" in result.stdout
