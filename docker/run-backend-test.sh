#!/usr/bin/env bash
# Backend TEST ENGINEER — black-box API integration tests (pytest against running server)
# Sees ONLY: tests/backend/ (rw) + contracts/ (ro) + its CI file
# CANNOT see backend/ or godot/ source code.
# Talks to the running API over the docker-compose network (host.docker.internal:8000).
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
AGENT="${AGENT:-claude-code}"   # arbitrator sets this

mkdir -p "$PROJECT_ROOT/.test_output" "$PROJECT_ROOT/tests/backend" "$PROJECT_ROOT/.github/workflows"
rm -f "$PROJECT_ROOT/.test_output/backend.json"

docker run --rm -it \
  --memory=1.5g --memory-swap=2g \
  --name gg-backend-test \
  --add-host=host.docker.internal:host-gateway \
  -v "$PROJECT_ROOT/tests/backend":/work/tests/backend \
  -v "$PROJECT_ROOT/contracts":/work/contracts:ro \
  -v "$PROJECT_ROOT/.github/workflows":/work/ci \
  -v "$PROJECT_ROOT/.test_output":/work/test_output \
  -w /work \
  -e API_BASE_URL="http://host.docker.internal:8000" \
  -e ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
  -e OPENAI_API_KEY="${OPENAI_API_KEY:-}" \
  growth-garden-test \
  "$AGENT"

# Must write before exiting:
# /work/test_output/backend.json
# {"status":"pass"|"fail", "summary":"...", "failures":[...], "log_tail":"..."}
# CI file it may edit: /work/ci/ci-backend.yml   (ONLY this one — not ci-frontend.yml)
