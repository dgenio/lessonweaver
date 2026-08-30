#!/usr/bin/env python3
"""Run the full local validation sequence — the same one CI runs (#290).

Why this exists
---------------
The required checks were written down in three places — ``.github/workflows/
ci.yml``, ``CONTRIBUTING.md`` and the pull-request template — and nothing kept
them in agreement. Three hand-maintained copies of a list drift, and the way
they drift is silent: a contributor runs the four commands they remember, every
one passes, and CI fails on the fifth.

So this script is the single place the sequence is written down, and
``tests/test_check_script.py`` fails if the workflow and this file stop
agreeing. CI keeps running the steps individually, because a failure named
``Type check`` is easier to read than a failure named ``check.py``; what the
test guarantees is that the two lists cannot diverge without someone noticing.

What it does not do
-------------------
It runs the checks and reports. It does not fix, format, or regenerate
anything — in particular the benchmark guard compares against the committed
``benchmark/v1/results.json`` and never rewrites it. Regeneration is a separate,
deliberate command, printed with the failure that calls for it.

There is no ``--fast`` mode. One was considered and left out: a partial run that
is not the required gate is another list to keep in sync, which is the problem
this file exists to remove.

Usage
-----
    python scripts/check.py           # run everything, stop-and-report at the end
    python scripts/check.py --list    # print the commands without running them
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import sysconfig
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# The canonical sequence. Order is deterministic and matches ci.yml's `test`
# job; `tests/test_check_script.py` asserts that correspondence.
#
# `kind` decides how the command is resolved:
#   "module"  -> run as `<this interpreter> -m <tool>`, so the check cannot pick
#                up a different `ruff`/`mypy`/`pytest` that happens to sit
#                earlier on PATH than the project's environment. CI runs them
#                bare, which is equivalent on a clean runner and not equivalent
#                on a developer machine.
#   "console" -> LessonWeaver's own entry point, resolved from this
#                interpreter's script directory for the same reason.
CHECKS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("Lint", "module", ("ruff", "check", "src/", "tests/")),
    ("Format check", "module", ("ruff", "format", "--check", "src/", "tests/")),
    ("Type check", "module", ("mypy", "src/lessonweaver/")),
    ("Run tests", "module", ("pytest",)),
    (
        "Guard detection benchmark",
        "console",
        (
            "lessonweaver",
            "eval-detection",
            "benchmark/v1/corpus.json",
            "--compare-results",
            "benchmark/v1/results.json",
        ),
    ),
)

# Printed when the benchmark guard fails, because that is the only failure here
# whose fix is "regenerate a committed artifact" rather than "change the code",
# and the command is easy to get wrong. Documented in
# docs/detection-benchmark.md; a deliberate change to detection behaviour
# regenerates this in the same pull request and explains the delta.
BENCHMARK_REGEN = "lessonweaver eval-detection benchmark/v1/corpus.json > benchmark/v1/results.json"


def display(argv: tuple[str, ...]) -> str:
    """The command as CI writes it — what a reader should recognise."""
    return " ".join(argv)


def resolve(kind: str, argv: tuple[str, ...]) -> list[str]:
    """Turn a declared command into one bound to this interpreter."""
    tool, *rest = argv
    if kind == "module":
        return [sys.executable, "-m", tool, *rest]
    scripts_dir = sysconfig.get_path("scripts")
    candidate = Path(scripts_dir) / tool
    if not candidate.exists():  # Windows layout, or an unusual install
        candidate = Path(scripts_dir) / f"{tool}.exe"
    return [str(candidate) if candidate.exists() else tool, *rest]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="check.py",
        description="Run the required validation sequence, in CI's order.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="print the commands and exit without running them",
    )
    args = parser.parse_args(argv[1:])

    if args.list:
        for name, _kind, command in CHECKS:
            print(f"{name}: {display(command)}")
        return 0

    failures: list[str] = []
    for name, kind, command in CHECKS:
        print(f"\n=== {name} ===")
        print(f"$ {display(command)}")
        completed = subprocess.run(resolve(kind, command), cwd=REPO_ROOT, check=False)
        if completed.returncode != 0:
            failures.append(name)
            print(f"--- {name} FAILED (exit {completed.returncode})")

    print("\n" + "=" * 60)
    if not failures:
        print(f"All {len(CHECKS)} checks passed.")
        return 0

    print(f"{len(failures)} of {len(CHECKS)} checks failed: {', '.join(failures)}")
    if "Guard detection benchmark" in failures:
        print(
            "\nThe benchmark guard compares against the committed scorecard and "
            "never rewrites it.\nIf the change to detection behaviour is "
            "deliberate, regenerate it in this pull request\nand explain the "
            f"delta (docs/detection-benchmark.md):\n\n    {BENCHMARK_REGEN}\n"
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
