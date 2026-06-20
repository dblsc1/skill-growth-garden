# Growth Garden — Frontend CLAUDE.md
# (place at: growth-garden/godot/CLAUDE.md)
# Also valid as AGENTS.md for Codex

## What This Package Is

Godot 4 frontend — isometric 2.5D pixel art garden game, exported as HTML5/WebAssembly.  
Mobile web first (375px phone viewport). Player walks in a forest that grows from diary entries.

## What You Can See (in this sandbox)

```
/work/godot/       ← your workspace (read + write)
/work/contracts/   ← API contracts (READ ONLY — never edit these)
```

**You cannot see backend/ — that is the backend agent's workspace.**  
All communication with backend happens through the API defined in contracts/.

## Project Structure

```
godot/
├── project.godot
├── scenes/
│   ├── Main.tscn                    # entry point, scene switcher
│   ├── Auth/
│   │   └── LoginScreen.tscn
│   └── Garden/
│       ├── GardenWorld.tscn         # main game scene
│       ├── PlayerCharacter.tscn
│       ├── ForestZone.tscn          # active skills zone
│       ├── PlaceholderZone.tscn     # warning tape zones (x3)
│       └── ui/
│           ├── DiaryInputPanel.tscn
│           ├── ConfirmationDialog.tscn
│           ├── ConfirmCard.tscn     # individual card within dialog
│           └── AssetDetailPanel.tscn
├── scripts/
│   ├── api/
│   │   └── ApiClient.gd    # ★ ALL HTTP requests go through here — no exceptions
│   ├── garden/
│   │   ├── GardenState.gd  # local state cache (loads from/saves to user://)
│   │   ├── ForestRenderer.gd
│   │   └── TreeSpawner.gd
│   └── ui/
│       ├── DiaryInputPanel.gd
│       ├── ConfirmationDialog.gd
│       └── AssetDetailPanel.gd
├── assets/
│   ├── sprites/
│   ├── ui/
│   └── audio/
└── tests/                   # GUT test scenes
```

## Hard Rules

- **All HTTP calls go through ApiClient.gd** — never use HTTPRequest directly elsewhere
- **All garden state goes through GardenState.gd** — never read/write user:// directly in other scripts
- **Never hardcode API URLs** — read from config/env
- **Asset rendering must be data-driven**: branch on `asset_type` string from API response, never hardcode asset type logic
- **Color tinting via `modulate`** — one sprite sheet per tree species, color_hex applied as shader tint
- **Never touch contracts/** — read only

## API Contract (what backend gives you)

Read `/work/contracts/openapi.json` and `/work/contracts/api_types.ts` for full types.  
Endpoints you call:
```
POST /api/v1/auth/register
POST /api/v1/auth/login
GET  /api/v1/garden/state      ← load on startup, cache locally
POST /api/v1/diary/extract     ← AI extraction
POST /api/v1/diary/confirm     ← write growth, get delta
PATCH /api/v1/garden/event/:id ← edit note from detail panel
```

Garden state structure (zones array):
```json
{
  "zones": [{
    "id": "...", "name": "...", "asset_type": "forest",
    "location": 1, "status": "active",
    "items": [{
      "id": "...", "name": "Python",
      "variant": {"species": "pine", "color_hex": "#2E6B3E", "display_name": "墨松"},
      "count": 12,
      "meta": {
        "recent_events": [
          {"tier3_name": "异步编程", "note": "编出第一个异步函数", "entry_date": "2026-05-09"}
        ]
      }
    }]
  }]
}
```

`location` maps to garden quadrant: 1=East 2=South 3=West 4=North.  
`status: "placeholder"` → render warning tape, no player interaction.

## Rendering Architecture

- Garden state loaded from server on login → cached in `GardenState.gd` (user://garden_cache.json)
- On app open (already logged in): render from cache instantly, sync in background
- On `/diary/confirm` response: apply delta to local cache (no full re-fetch)
- All rendering is client-side — server sends JSON counts only

## Signal Architecture

Cross-node communication uses signals only — never get_parent() or $NodePath to siblings:

```gdscript
# Required signals — define these, don't invent new coupling patterns
signal diary_submitted(text: String)
signal extraction_received(extractions: Array)
signal card_confirmed(item_id: String, tier3: String, note: String)
signal garden_updated(delta: Dictionary)
signal asset_tapped(item: Dictionary)
signal note_edit_requested(event_id: String, current_note: String)
```

## GDScript Doc Convention

```gdscript
## One-line file purpose at top of every .gd file

## What this function does (contract, not implementation)
## Args: text (String) — diary content from user input
## Returns: void. Emits: diary_submitted signal
## Side effects: shows loading state
func submit_diary(text: String) -> void:
```

## Run & Check

```bash
# From host machine (Godot runs on host, not in container)
gdtoolkit --check godot/scripts/   # lint GDScript (runs in container via make)
make check-frontend                 # lint only (export happens in CI)
```

## Your Role Is Not Fixed

The arbitrator assigns roles per task. This session you may be the **worker** (you write code)
or the **reviewer** (read-only — inspect and report, cannot modify). The launch script told
you which. Codex and Claude Code are interchangeable for either role.

## AI Work-Trail (REQUIRED — for humans, git-committed)

If you are the **worker**, before writing your status file, write a devlog entry:
`docs/devlog/YYYY-MM-DD-<slug>.md` covering **What / Why / Decisions / Contract impact / Tests**.
Emphasis on **Why**. The arbitrator commits it with your code. See
`vibecoding/05-AI工作留痕-文档管理.md`. Do NOT push (only the arbitrator pushes).

## When You Finish (REQUIRED)

Write this file before exiting so the pipeline knows you're done:

**Worker** (`/work/godot/.agent_status.json`):
```json
{
  "status": "done",
  "summary": "implemented X scene, wired signals, contracts unchanged",
  "contracts_changed": false
}
```

**Reviewer** (`/work/review_output/frontend.json`):
```json
{
  "status": "approved",
  "issues": [],
  "summary": "GDScript structure correct, API calls match contracts"
}
```

If you are the **reviewer**: godot/ is read-only. You CANNOT write there.  
Write ONLY to `/work/review_output/frontend.json`.

## Forbidden

- Direct HTTPRequest nodes outside ApiClient.gd
- Direct user:// file access outside GardenState.gd
- Hardcoded API base URL (use config)
- `get_parent()` or `$AbsolutePath` for cross-scene node access — use signals
- Reading or writing contracts/ (read only)
