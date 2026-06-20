# API Specification
# Growth Garden — MVP

**Version**: 0.2 — MVP Only  
**Status**: Authoritative contract — discuss before changing  
**Last Updated**: 2026-06-19  
**Base URL**: `https://api.yourdomain.com/api/v1`  
**Auth**: Bearer JWT in `Authorization` header  

---

## Endpoints (5 total)

---

### 1. POST /auth/register

**Request**
```json
{
  "email": "string",
  "password": "string",
  "username": "string"
}
```

**Response 201**
```json
{
  "token": "string (JWT)",
  "user": {
    "id": "string",
    "username": "string",
    "tier": "free"
  }
}
```

**Errors**: `409` email or username taken · `422` validation failed

---

### 2. POST /auth/login

**Request**
```json
{
  "email": "string",
  "password": "string"
}
```

**Response 200**
```json
{
  "token": "string (JWT)",
  "user": {
    "id": "string",
    "username": "string",
    "tier": "string"
  }
}
```

**Errors**: `401` wrong credentials

---

### 3. GET /garden/state

Loaded once at app start. Godot maintains local state after this; use confirm delta to update.

**Response 200**
```json
{
  "zones": [
    {
      "id": "zone_abc123",
      "name": "我的技能森林",
      "asset_type": "forest",
      "location": 1,
      "status": "active",
      "items": [
        {
          "id": "item_xyz",
          "name": "钢琴",
          "variant": {
            "species": "bamboo",
            "color_hex": "#5E8C4A",
            "display_name": "青竹"
          },
          "count": 12,
          "meta": {
            "created_at": "2026-01-15",
            "last_entry_date": "2026-06-18",
            "recent_events": [
              {
                "tier3_name": "异步编程",
                "note": "编出第一个异步函数",
                "entry_date": "2026-05-09"
              },
              {
                "tier3_name": "类型标注",
                "note": "完成了整个模块",
                "entry_date": "2026-05-15"
              }
            ]
          }
        }
      ]
    },
    {
      "id": "zone_def456",
      "name": "花丛",
      "asset_type": "flower_patch",
      "location": 2,
      "status": "placeholder",
      "items": []
    },
    {
      "id": "zone_ghi789",
      "name": "鱼塘",
      "asset_type": "fish_pond",
      "location": 3,
      "status": "placeholder",
      "items": []
    },
    {
      "id": "zone_jkl012",
      "name": "星空",
      "asset_type": "starry_sky",
      "location": 4,
      "status": "placeholder",
      "items": []
    }
  ]
}
```

**Field notes**:
- `location`: 1=East 2=South 3=West 4=North — Godot uses this to place the zone on the map
- `asset_type`: tells Godot which rendering system to use — never hardcode asset_type logic in Godot, always branch on this field
- `status: placeholder` → Godot renders warning tape + placeholder art, no interaction
- `variant.color_hex`: Godot applies as shader color tint over the species sprite sheet — one sprite sheet per species, infinite color variants

---

### 4. POST /diary/extract

Sends diary text to AI. Returns extracted skill items for user to confirm. Does **not** write to DB.

**Request**
```json
{
  "text": "string (diary content, local only — not stored server-side)",
  "entry_date": "string (YYYY-MM-DD)"
}
```

**Response 200**
```json
{
  "extractions": [
    {
      "tier2_name": "钢琴",
      "tier3_name": "视奏练习",
      "note": "练了一小时视奏，完成了第三首曲子",
      "is_new_skill": false,
      "existing_item_id": "item_xyz",
      "suggested_variant": null,
      "raw_mention": "练了一小时钢琴视奏，完成了第三首曲子",
      "meta": {
        "context": "music practice session"
      }
    },
    {
      "tier2_name": "Python",
      "tier3_name": "异步编程",
      "is_new_skill": true,
      "existing_item_id": null,
      "suggested_variant": {
        "species": "pine",
        "color_hex": "#2E6B3E",
        "display_name": "墨松"
      },
      "raw_mention": "学了Python的asyncio",
      "meta": {
        "context": "programming study"
      }
    }
  ]
}
```

**Field notes**:
- `note`: AI-extracted summary from `raw_mention`. User can edit this in the confirmation card before confirming. Stored as-is after confirm.
- `is_new_skill: true` → `suggested_variant` is populated (server randomly generates at extract time)
- `is_new_skill: false` → `suggested_variant` is null, `existing_item_id` is populated
- Godot renders each extraction as one confirmation card
- New skill card shows `suggested_variant` tree preview before user confirms
- Diary text is never stored server-side — only `entry_date` is logged in ai_usage

**Errors**: `402` free tier limit · `429` rate limit · `504` AI unavailable

---

### 5. POST /diary/confirm

User's confirmed selections. Writes to DB. Returns delta for Godot to update local state without re-fetching /garden/state.

**Request**
```json
{
  "entry_date": "string (YYYY-MM-DD)",
  "confirmed": [
    {
      "existing_item_id": "item_xyz",
      "tier3_name": "视奏练习",
      "note": "练了一小时视奏，完成了第三首曲子",
      "suggested_variant": null
    },
    {
      "existing_item_id": null,
      "tier2_name": "Python",
      "tier3_name": "异步编程",
      "suggested_variant": {
        "species": "pine",
        "color_hex": "#2E6B3E",
        "display_name": "墨松"
      }
    }
  ]
}
```

**Response 200**
```json
{
  "growth_delta": [
    {
      "item_id": "item_xyz",
      "new_total_count": 13
    }
  ],
  "new_items": [
    {
      "id": "item_new_abc",
      "name": "Python",
      "variant": {
        "species": "pine",
        "color_hex": "#2E6B3E",
        "display_name": "墨松"
      },
      "count": 1,
      "meta": {
        "created_at": "2026-06-19",
        "last_entry_date": "2026-06-19"
      }
    }
  ]
}
```

**Field notes**:
- `growth_delta`: existing items that gained count — Godot adds tree elements for each
- `new_items`: newly created items — Godot adds new tree species to the forest
- Server validates `suggested_variant.species` against allowed species list before writing
- Skipped extractions (user dismissed cards) are simply absent from `confirmed` array

**Errors**: `400` invalid item_id · `409` entry_date already confirmed

---

## Standard Error Format

```json
{
  "error": "ERROR_CODE",
  "message": "Human readable description"
}
```

| Code | HTTP | Meaning |
|---|---|---|
| `UNAUTHORIZED` | 401 | Missing or invalid JWT |
| `FREE_LIMIT_REACHED` | 402 | Monthly diary limit hit |
| `RATE_LIMITED` | 429 | Too many AI calls (10/hour) |
| `AI_UNAVAILABLE` | 504 | DeepSeek + GPT-4o both failed |
| `ALREADY_CONFIRMED` | 409 | This entry_date was already confirmed |

---

---

### 6. PATCH /garden/event/:event_id

Edit note on an already-confirmed growth event. Triggered from the asset detail panel.

**Request**
```json
{ "note": "string (user-edited, max 200 chars)" }
```

**Response 200**
```json
{ "event_id": "string", "note": "string" }
```

**Errors**: `404` event not found · `403` not your event

---

## What is NOT in MVP

- Friend system endpoints
- Category management endpoints  
- Zone configuration endpoints
- Voice input endpoint
- Password reset

These will be added in later versions without breaking the above contracts.
