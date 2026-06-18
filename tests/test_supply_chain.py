"""Supply-chain configuration checks."""

from __future__ import annotations

import re
from pathlib import Path

WORKFLOW_DIR = Path(".github/workflows")
SHA_REF_RE = re.compile(r"uses:\s+([^@\s]+)@([0-9a-f]{40})(?:\s+#\s*(\S.*))?")
FLOATING_REF_RE = re.compile(r"uses:\s+[^@\s]+@(?![0-9a-f]{40}\b)[^\s#]+")


def _workflow_text() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(WORKFLOW_DIR.glob("*.yml"))
    )


def test_third_party_actions_are_pinned_to_sha_with_version_comments() -> None:
    workflow_text = _workflow_text()

    assert not FLOATING_REF_RE.search(workflow_text)
    pinned_actions = SHA_REF_RE.findall(workflow_text)
    assert pinned_actions
    assert {action for action, _, _ in pinned_actions} >= {
        "actions/checkout",
        "actions/setup-python",
        "pypa/gh-action-pypi-publish",
        "ossf/scorecard-action",
    }
    assert all(
        comment.startswith("v") or comment.startswith("release/")
        for _, _, comment in pinned_actions
    )


def test_dependabot_covers_actions_and_python_dev_dependencies() -> None:
    dependabot = Path(".github/dependabot.yml").read_text(encoding="utf-8")

    assert 'package-ecosystem: "github-actions"' in dependabot
    assert 'package-ecosystem: "pip"' in dependabot
    assert "groups:" in dependabot
    assert "dev-dependencies" in dependabot


def test_scorecard_workflow_publishes_sarif_on_a_schedule() -> None:
    scorecard = Path(".github/workflows/scorecard.yml").read_text(encoding="utf-8")

    assert "schedule:" in scorecard
    assert "security-events: write" in scorecard
    assert "id-token: write" in scorecard
    assert "contents: read" in scorecard
    assert "ossf/scorecard-action@" in scorecard
    assert "results_format: sarif" in scorecard
    assert "publish_results: true" in scorecard


def test_publish_workflow_enables_pypi_attestations() -> None:
    publish = Path(".github/workflows/publish.yml").read_text(encoding="utf-8")

    assert "id-token: write" in publish
    assert "attestations: true" in publish


def test_security_policy_documents_supply_chain_verification() -> None:
    security = Path("SECURITY.md").read_text(encoding="utf-8")

    assert "## Supply chain" in security
    assert "zero runtime dependencies" in security
    assert "Trusted Publishing" in security
    assert "attestations" in security
    assert "verify" in security.lower()
