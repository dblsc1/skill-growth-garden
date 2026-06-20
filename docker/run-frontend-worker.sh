#!/usr/bin/env bash
# Frontend WORKER — read/write access to godot/
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
AGENT="${AGENT:-claude-code}"

rm -f "$PROJECT_ROOT/godot/.agent_status.json"

docker run --rm -it \
  --memory=1g --memory-swap=1.5g \
  --name gg-frontend-worker \
  -v "$PROJECT_ROOT/godot":/work/godot \
  -v "$PROJECT_ROOT/contracts":/work/contracts:ro \
  -w /work \
  -e ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
  -e OPENAI_API_KEY="${OPENAI_API_KEY:-}" \
  growth-garden-frontend \
  "$AGENT"

# Agent must write before exiting:
# /work/godot/.agent_status.json
# {"status": "done"|"failed", "summary": "...", "contracts_changed": false}
