#!/usr/bin/env bash
# Backend WORKER — read/write access to backend/
# Complexity: simple → AGENT=codex, complex → AGENT=claude-code (default)
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
AGENT="${AGENT:-claude-code}"   # override with: AGENT=codex bash run-backend-worker.sh

# Clean previous status
rm -f "$PROJECT_ROOT/backend/.agent_status.json"

docker run --rm -it \
  --memory=1g --memory-swap=1.5g \
  --name gg-backend-worker \
  -v "$PROJECT_ROOT/backend":/work/backend \
  -v "$PROJECT_ROOT/contracts":/work/contracts:ro \
  -w /work \
  -e ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
  -e OPENAI_API_KEY="${OPENAI_API_KEY:-}" \
  growth-garden-backend \
  "$AGENT"

# Agent must write before exiting:
# /work/backend/.agent_status.json
# {"status": "done"|"failed", "summary": "...", "contracts_changed": false}
