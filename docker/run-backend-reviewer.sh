#!/usr/bin/env bash
# Backend REVIEWER — backend/ is READ-ONLY, cannot modify any code
# Always the opposite agent from the worker (simple→claude-code, complex→codex)
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
AGENT="${AGENT:-claude-code}"

mkdir -p "$PROJECT_ROOT/.review_output"
rm -f "$PROJECT_ROOT/.review_output/backend.json"

docker run --rm -it \
  --memory=1g --memory-swap=1.5g \
  --name gg-backend-reviewer \
  -v "$PROJECT_ROOT/backend":/work/backend:ro \
  -v "$PROJECT_ROOT/contracts":/work/contracts:ro \
  -v "$PROJECT_ROOT/.review_output":/work/review_output \
  -w /work \
  -e ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
  -e OPENAI_API_KEY="${OPENAI_API_KEY:-}" \
  growth-garden-backend \
  "$AGENT"

# Reviewer must write before exiting:
# /work/review_output/backend.json
# {"status": "approved"|"needs_revision", "issues": ["..."], "summary": "..."}
# NOTE: backend/ is :ro — any attempt to write will fail at the OS level
