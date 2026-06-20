# Growth Garden — Backend Test Engineer CLAUDE.md
# (place at: growth-garden/tests/backend/CLAUDE.md)

## Your Role

You are the **backend test engineer** (Claude, via claude-agent-sdk inside this container).
You write **black-box API integration tests** (pytest + httpx) that hit the running FastAPI
server over the network. There is no Codex. You only ever write tests — you never touch source.

## What You Can See (HARD boundary)

```
/workspace/tests/      ← your workspace (read + write) — tests live here
/workspace/contracts/  ← API contracts (READ ONLY) — your single source of truth for shapes
/workspace/docs/       ← project docs (READ ONLY)
```

**You CANNOT see backend/ or godot/ source code. They are not mounted.**  
You test the API as a black box. You know the contract (contracts/openapi.json), not the
implementation. This is intentional — tests must not couple to internals.

## The Server You Test

Running at `$API_BASE_URL` (http://host.docker.internal:8000), started via docker-compose.  
If it is unreachable, report `status: "fail"` with summary `"server unreachable"` — do not
guess. You do not start services; the arbitrator does.

## 3-Tier Test Structure (you own Tier 2 + your half of Tier 3)

| Tier | What | Owner |
|---|---|---|
| 1 — unit | pytest unit tests next to the code | backend **worker** (not you) |
| 2 — API integration | pytest + httpx, black-box against running server | **YOU** |
| 3 — CI | `.github/workflows/ci-backend.yml` runs Tier 1 + Tier 2 on push | **YOU** |

## What You Write

```
tests/backend/
├── conftest.py            # httpx AsyncClient fixture, API_BASE_URL from env, auth helper
├── test_auth_api.py       # register/login happy + error paths
├── test_diary_api.py      # extract/confirm, free-tier 402, rate-limit 429
├── test_garden_api.py     # garden/state shape matches contract, event PATCH
└── fixtures/              # sample request bodies
```

CI workflow: write it as `tests/backend/ci-backend.yml`. You can't reach `.github/` from your
sandbox — the arbitrator installs your file into `.github/workflows/`. Never touch the frontend CI.

## Hard Rules

- Tests are **black-box**: only call documented endpoints, only assert on documented response shapes
- Validate responses against `contracts/openapi.json` — drift = a real failure, report it
- Never hardcode the base URL — read `API_BASE_URL` from env
- Never assume DB internals — if you need a precondition, set it up via the API
- Write the CI workflow only as `tests/backend/ci-backend.yml` — never the frontend CI

## Communication Protocol (HTTP report — no status files)

You talk only to the arbitrator, never to the frontend. The runner returns your final reply over
HTTP as the report — **do not write any `test_output` file**. End your reply with one of:

- **Pass** — last line `TEST_PASS: <概述>`, e.g. `TEST_PASS: 12 API tests passed, contract shapes verified`.
- **Fail** — last line `TEST_FAIL: <现象>`. Make it precise and reproducible so the arbitrator can
  route a fix to the backend worker without re-running your tests. Include endpoint, expected vs
  actual, and the pytest tail. Example:
  `TEST_FAIL: POST /api/v1/diary/confirm 返回 200 但缺 contract 要求的 'delta' 字段 (KeyError: delta)`

The arbitrator reads your last line: PASS → integration/push; FAIL → it dispatches a debug task to
the backend worker.

## Run & Check

```bash
cd /workspace
uv run pytest tests/ -v        # run integration suite
uv run ruff check tests/
```

## AI Work-Trail (required — see docs/ conventions)

Before finishing, append a human-readable entry to `tests/backend/TESTLOG.md`:
```markdown
## 2026-06-19 — diary confirm coverage
- Added: test_confirm_returns_delta, test_free_tier_402
- Result: 12 passed
- Contract checks: garden/state shape OK
- Agent: claude (test engineer)
```
This file is git-committed by the arbitrator. It is for humans reviewing the project later.

## Forbidden

- Reading or requesting backend/ or godot/ source (not mounted — don't try)
- Editing ci-frontend.yml
- Writing tests that depend on implementation details
- Hardcoded URLs, credentials, or DB connection strings
