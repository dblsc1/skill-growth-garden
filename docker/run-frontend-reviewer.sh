#!/usr/bin/env bash
# Frontend REVIEWER — godot/ is READ-ONLY, cannot modify any code
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
AGENT="${AGENT:-claude-code}"

mkdir -p "$PROJECT_ROOT/.review_output"
rm -f "$PROJECT_ROOT/.review_output/frontend.json"

docker run --rm -it \
  --memory=1g --memory-swap=1.5g \
  --name gg-frontend-reviewer \
  -v "$PROJECT_ROOT/godot":/work/godot:ro \
  -v "$PROJECT_ROOT/contracts":/work/contracts:ro \
  -v "$PROJECT_ROOT/.review_output":/work/review_output \
  -w /work \
  -e ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
  -e OPENAI_API_KEY="${OPENAI_API_KEY:-}" \
  growth-garden-frontend \
  "$AGENT"

# Reviewer must write before exiting:
# /work/review_output/frontend.json
# {"status": "approved"|"needs_revision", "issues": ["..."], "summary": "..."}
