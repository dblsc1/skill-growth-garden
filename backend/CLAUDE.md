# Growth Garden — Backend CLAUDE.md
# (place at: growth-garden/backend/CLAUDE.md)

## What This Package Is

FastAPI backend. Handles auth, diary AI extraction, garden state, free tier limits.  
Runs on Alibaba Cloud ECS (Ubuntu, 2C2G). MongoDB self-hosted on same ECS.

## What You Can See (in this sandbox)

```
/work/backend/     ← your workspace (read + write)
/work/contracts/   ← API contracts (READ ONLY — never edit these directly)
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

Read `/work/contracts/openapi.json` for the ground truth on all request/response shapes.  
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

Schema: read `/work/contracts/db_schema.md` (synced from tech_layer/DB_Schema.md).  
`count` is never stored — always aggregated from growth_events.

## Key Constraints

- **ECS: 2C 2G RAM** — no heavy operations in request path
- MongoDB WiredTiger cache: 0.25GB (configured in mongod.conf — don't change)
- FastAPI: max 2 uvicorn workers
- Rate limit: POST /diary/extract → 10 calls/hour per user (enforce in middleware)
- Free tier: 10 diary entries/month per user → HTTP 402 on breach

## Run & Check

```bash
cd /work/backend
uv sync                      # install deps
uv run uvicorn main:app --reload   # dev server
uv run pytest tests/         # run tests
uv run ruff check .          # lint
uv run ruff format .         # format
make check                   # lint + type check + tests (run before finishing)
```

## Your Role Is Not Fixed

The arbitrator assigns roles per task. This session you may be the **worker** (you write code)
or the **reviewer** (read-only — you inspect and report, you cannot modify). The launch script
told you which. Codex and Claude Code are interchangeable for either role — don't assume.

## AI Work-Trail (REQUIRED — for humans, git-committed)

If you are the **worker**, before writing your status file, write a devlog entry:
`docs/devlog/YYYY-MM-DD-<slug>.md` covering **What / Why / Decisions / Contract impact / Tests**.
The arbitrator commits it alongside your code. Emphasis on **Why** — code shows what, devlog
shows why. See `vibecoding/05-AI工作留痕-文档管理.md`. Do NOT push (only the arbitrator pushes).

## When You Finish (REQUIRED)

Write this file before exiting so the pipeline knows you're done:

**Worker** (`/work/backend/.agent_status.json`):
```json
{
  "status": "done",
  "summary": "implemented X, added tests, contracts unchanged",
  "contracts_changed": false
}
```

**Reviewer** (`/work/review_output/backend.json`):
```json
{
  "status": "approved",
  "issues": [],
  "summary": "code looks correct, matches API contract"
}
```

If you are the **reviewer**: you are in a read-only Docker mount. You CANNOT write to backend/.  
Write ONLY to `/work/review_output/backend.json`. This is your only output channel.

## Forbidden

- Hardcoded API keys, passwords, or connection strings anywhere in code
- Raw diary text in any log, DB field, or external call (except DeepSeek/GPT for extraction)
- Synchronous MongoDB calls (use motor async driver)
- Deleting or rewriting migration history
- Direct writes to contracts/ (read only)
