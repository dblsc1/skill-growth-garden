# Growth Garden — Backend CLAUDE.md
# (place at: growth-garden/backend/CLAUDE.md)

## What This Package Is

FastAPI backend. Handles auth, diary AI extraction, garden state, free tier limits.  
Runs on Alibaba Cloud ECS (Ubuntu, 2C2G). MongoDB self-hosted on same ECS.

## What You Can See (in this sandbox)

```
/workspace/backend/     ← your workspace (read + write)
/workspace/contracts/   ← API contracts (READ ONLY — never edit these directly)
```

**You cannot see godot/ — that is the frontend agent's workspace.**  
Collaboration happens only through contracts/.

## Package Structure

```
backend/
├── main.py              # FastAPI app entry, router registration only
├── config.py            # env var loading (Pydantic Settings)
├── routers/
│   ├── auth.py          # POST /auth/register, /auth/login
│   ├── diary.py         # POST /diary/extract, /diary/confirm
│   ├── garden.py        # GET /garden/state
│   └── events.py        # PATCH /garden/event/:id
├── models/              # Pydantic request/response schemas
│   ├── auth.py
│   ├── diary.py
│   └── garden.py
├── services/
│   └── ai_extraction.py # DeepSeek/GPT orchestration — all AI calls go here
├── db/
│   └── mongo.py         # connection singleton + collection accessors
└── tests/
    ├── test_auth.py
    ├── test_diary.py
    ├── test_garden.py
    └── ai_fixtures/     # sample diaries + expected extractions (ground truth)
```

## Hard Rules

- **All routes versioned**: `/api/v1/...`
- **All Pydantic models go in models/** — never inline in routers
- **All MongoDB access goes through db/mongo.py** — never call pymongo directly in routers
- **All AI calls go through services/ai_extraction.py** — never call DeepSeek API in routers
- **Never put business logic in routers** — routers call services, services do work
- **Never touch godot/ or contracts/** (contracts/ is read-only, you can read but not write)
- **Diary text must never be logged, stored, or passed to any external service beyond DeepSeek/GPT**

## API Contracts (authoritative)

Read `/workspace/contracts/openapi.json` for the ground truth on all request/response shapes.  
The 6 endpoints you implement:
```
POST /api/v1/auth/register
POST /api/v1/auth/login
GET  /api/v1/garden/state
POST /api/v1/diary/extract
POST /api/v1/diary/confirm
PATCH /api/v1/garden/event/:event_id
```

If you need to change a response shape → update the Pydantic model → run `make sync-contracts` → the frontend agent will pick up the new TS types.

## MongoDB Collections

```
users, zones, growth_items, growth_events, ai_usage
```

Schema: read `/workspace/contracts/db_schema.md` (synced from tech_layer/DB_Schema.md).  
`count` is never stored — always aggregated from growth_events.

## Key Constraints

- **ECS: 2C 2G RAM** — no heavy operations in request path
- MongoDB WiredTiger cache: 0.25GB (configured in mongod.conf — don't change)
- FastAPI: max 2 uvicorn workers
- Rate limit: POST /diary/extract → 10 calls/hour per user (enforce in middleware)
- Free tier: 10 diary entries/month per user → HTTP 402 on breach

## Run & Check

```bash
cd /workspace/backend
uv sync                      # install deps
uv run uvicorn main:app --reload   # dev server
uv run pytest tests/         # run tests
uv run ruff check .          # lint
uv run ruff format .         # format
make check                   # lint + type check + tests (run before finishing)
```

## Your Role

You are **the backend agent** (Claude, via claude-agent-sdk inside this container). There is no
Codex and no separate reviewer — code review is done by the arbitrator. The arbitrator may ask
you to self-review or to fix bugs it found; just follow the task it sends you over `/task`.

## AI Work-Trail (REQUIRED — for humans, git-committed)

Maintain your own docs under `/workspace/backend/docs/`:
- `dev-log.md` — append **What / Why / Decisions / Contract impact / Tests** per task (emphasis on **Why**).
- `structure.md` — keep a short map of backend/ files and their responsibilities up to date.
- `self-constraints.md` — record how you kept files small, low-coupling, multi-file (the arbitrator checks this).

`audit.log` is written automatically by the runner — don't touch it. The global `/workspace/docs/`
is READ-ONLY; only write inside `/workspace/backend/docs/`. See `/workspace/docs/architecture/05-*`.
Do NOT push or commit — only the arbitrator does.

## When You Finish

**No status files.** The runner automatically returns your final reply to the arbitrator over HTTP
as the task report. Before you finish:
1. `make check` is green (lint + types + tests).
2. You updated `docs/dev-log.md` and `docs/structure.md`.
3. End with a one-paragraph summary: what you delivered, whether contracts changed, what's untested.

If you need something outside your sandbox (touch contracts/, git, read another package), you can't —
ask the arbitrator in your reply; sensitive tool calls are intercepted and routed to it for approval.

## Forbidden

- Hardcoded API keys, passwords, or connection strings anywhere in code
- Raw diary text in any log, DB field, or external call (except DeepSeek/GPT for extraction)
- Synchronous MongoDB calls (use motor async driver)
- Deleting or rewriting migration history
- Direct writes to contracts/ (read only)
