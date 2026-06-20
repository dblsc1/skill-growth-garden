#!/usr/bin/env bash
# Frontend TEST ENGINEER — Playwright browser E2E against the running web build
# Sees ONLY: tests/frontend/ (rw) + contracts/ (ro) + its CI file
# CANNOT see backend/ or godot/ source code.
# Drives the exported Godot HTML5 build over the network (host.docker.internal:8080).
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
AGENT="${AGENT:-claude-code}"

mkdir -p "$PROJECT_ROOT/.test_output" "$PROJECT_ROOT/tests/frontend" "$PROJECT_ROOT/.github/workflows"
rm -f "$PROJECT_ROOT/.test_output/frontend.json"

docker run --rm -it \
  --memory=2g --memory-swap=2.5g \
  --name gg-frontend-test \
  --add-host=host.docker.internal:host-gateway \
  -v "$PROJECT_ROOT/tests/frontend":/work/tests/frontend \
  -v "$PROJECT_ROOT/contracts":/work/contracts:ro \
  -v "$PROJECT_ROOT/.github/workflows":/work/ci \
  -v "$PROJECT_ROOT/.test_output":/work/test_output \
  -w /work \
  -e WEB_BASE_URL="http://host.docker.internal:8080" \
  -e API_BASE_URL="http://host.docker.internal:8000" \
  -e ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
  -e OPENAI_API_KEY="${OPENAI_API_KEY:-}" \
  growth-garden-test \
  "$AGENT"

# Must write before exiting:
# /work/test_output/frontend.json
# {"status":"pass"|"fail", "summary":"...", "failures":[...], "log_tail":"..."}
# CI file it may edit: /work/ci/ci-frontend.yml   (ONLY this one — not ci-backend.yml)
