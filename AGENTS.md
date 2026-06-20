# Growth Garden — Root CLAUDE.md

## Project Overview

Growth Garden: users write diary entries → AI extracts skills → pixel-art 2.5D forest grows.

**Stack**: Godot 4 (frontend, GDScript) + Python FastAPI (backend) + MongoDB + DeepSeek API  
**Platform**: Mobile web first (Godot HTML5 export)

## Monorepo Structure

```
growth-garden/
├── contracts/      # ★ Single source of truth — API contracts
│   ├── openapi.json          # auto-generated from FastAPI
│   └── api_types.ts          # auto-generated from openapi.json
├── backend/        # FastAPI — see backend/CLAUDE.md
├── godot/          # Godot 4 — see godot/CLAUDE.md
├── tests/          # backend/ (API 黑盒) + frontend/ (Playwright E2E) — 测试工程师
├── docker/         # agent 沙箱镜像 + compose（容器内跑 agent-runner）
└── orchestrator/   # 宿主机裁决者（LangGraph，建设中）— see orchestrator/CLAUDE.md
```

## Hard Rules (apply everywhere)

- **Never commit secrets or API keys** — use .env only
- **Never store diary text on the server** — it stays in browser IndexedDB only
- **contracts/ is the only shared source of truth** — if you change an API, update contracts/ first
- **Never push directly to main or develop** — PR only, CI must pass

## Pre-commit Self-Check

Before finishing any task, verify:
```
□ Changes only in your assigned package? (backend/ or godot/)
□ Changed an API endpoint or schema? → update contracts/openapi.json + run make sync-contracts
□ make check passes (lint + type check)?
□ No hardcoded secrets or localhost URLs?
□ Comments only explain WHY, not WHAT?
```

## Contracts Sync (mandatory when backend model changes)

```bash
make sync-contracts   # regenerates contracts/api_types.ts from FastAPI OpenAPI output
```

If you change a Pydantic model in backend/ → you MUST run this. Godot agent depends on these types.

## Key Documents (read these, don't re-derive)

- `contracts/openapi.json` — authoritative API contract (6 endpoints, auto-generated)
- `contracts/db_schema.md` — MongoDB collections
- `docs/architecture/README.md` — 现行多 agent 架构（容器隔离 + 裁决者审批 + 人批 contract）
