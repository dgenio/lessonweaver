#!/usr/bin/env bash
#
# Reproducible ~60-second terminal demo of lessonweaver's closed loop:
# a coding-agent failure -> detect -> review -> approve -> export a skill card
# -> load it back into agent context. This script is the source used to record
# the README demo GIF/asciinema cast; run it as-is to reproduce that flow.
#
# Usage (from the repository root):
#   bash docs/assets/demo.sh
#   asciinema rec demo.cast -c "bash docs/assets/demo.sh"   # to record
#
# It writes only to a throwaway registry under a temp dir and cleans up after.

set -euo pipefail

REG="$(mktemp -d)/registry"
TRACE="examples/closed_loop_contextweaver/traces/agent_merged_without_tests.json"
CANDIDATE="trace-closed-loop-merge-without-tests-001-human-correction"
SKILL="skill-${CANDIDATE}"

trap 'rm -rf "$(dirname "$REG")"' EXIT

echo "# 1. A coding agent merged a PR from its title and a human had to revert it."
echo "#    Detect the candidate lesson from the trace:"
lessonweaver detect "$TRACE" --save --registry-root "$REG"

echo
echo "# 2. The human review gate: record an approve decision."
lessonweaver answer "$CANDIDATE" decision approve \
  --free-text "Run the full test suite and confirm it passes before merging any PR." \
  --registry-root "$REG"

echo
echo "# 3. Approve the candidate into a reviewed lesson and skill."
lessonweaver approve "$CANDIDATE" --approved-by reviewer --registry-root "$REG"

echo
echo "# 4. Export the reviewed skill as an AGENTS.md fragment..."
lessonweaver export-skill "$SKILL" --format agents-md --redact --registry-root "$REG"

echo
echo "# 5. ...and as a skill card (the format contextweaver loads back into context)."
lessonweaver export-skill "$SKILL" --format json --redact --registry-root "$REG"

echo
echo "# Done: a real failure is now a reviewed, governed skill the next run can load."
