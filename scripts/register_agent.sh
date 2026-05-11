#!/usr/bin/env bash
# register_agent.sh — Fetch the live agent card from the deployed orchestrator
# and write it to registration/orchestrator-card.json for Prompt Opinion submission.
#
# Usage:
#   ORCHESTRATOR_URL=https://discharge-orchestrator-xxx.a.run.app \
#     bash scripts/register_agent.sh
#
# The output file is what you paste / upload into the Prompt Opinion workspace.

set -euo pipefail

ORCHESTRATOR_URL="${ORCHESTRATOR_URL:?Set ORCHESTRATOR_URL to your deployed orchestrator URL}"
CARD_URL="${ORCHESTRATOR_URL}/.well-known/agent-card.json"
OUT="registration/orchestrator-card.json"

echo "Fetching agent card from: ${CARD_URL}"
curl -fsSL "${CARD_URL}" | python3 -m json.tool > "${OUT}"
echo "Saved → ${OUT}"
echo ""
echo "Next steps:"
echo "  1. Go to app.promptopinion.ai → your workspace → Agents → Add Agent"
echo "  2. Enter the Agent URL: ${ORCHESTRATOR_URL}"
echo "  3. Prompt Opinion will fetch the card automatically."
echo "  4. Set the X-API-Key secret to match AGENT_API_KEY in your deployment."
