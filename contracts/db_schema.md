# Database Schema Document
# Growth Garden — MVP

**Version**: 0.2 — MVP Only  
**Status**: Draft  
**Last Updated**: 2026-06-19  
**Engine**: MongoDB self-hosted on ECS  
**Database name**: `growth_garden`  

---

## Design Principles

**Flexible asset architecture**: `asset_type` is always a string key, never a hardcoded enum in application logic. Adding a new asset type = add sprite assets + update Godot renderer — no schema migration needed.

**Diary text never touches the server**: Only `entry_date` and metadata are stored. Raw diary content stays in browser IndexedDB (Godot `user://`).

**Local-first rendering**: `/garden/state` is fetched once on login. Godot maintains local state. `/diary/confirm` returns a delta to patch local state without re-fetching.

---

## Collections (4 for MVP)

---

### 1. `users`

```json
{
  "_id": "ObjectId",
  "email": "string",
  "password_hash": "string (bcrypt)",
  "username": "string",
  "tier": "string (free | paid)",
  "diary_count_this_month": "int",
  "diary_month_key": "string (YYYY-MM, for reset detection)",
  "created_at": "datetime"
}
```

**Indexes**: `email` unique · `username` unique

---

### 2. `zones`

One document per garden zone per user. MVP users have 4 zones (1 active, 3 placeholder).

```json
{
  "_id": "ObjectId",
  "user_id": "ObjectId",
  "name": "string (user-defined, e.g. '我的技能森林')",
  "asset_type": "string (e.g. 'forest' | 'flower_patch' | 'fish_pond' | 'starry_sky')",
  "location": "int (1=East | 2=South | 3=West | 4=North)",
  "status": "string (active | placeholder)",
  "created_at": "datetime"
}
```

**Indexes**: `user_id` · `(user_id, location)` unique compound

**MVP state**: seeded at registration with 4 zones — 1 active (forest, location TBD by user at onboarding), 3 placeholder.

---

### 3. `growth_items`

One document per skill (or future: flower type, fish type, star cluster) per user. This is the Tier-2 level — the thing that grows.

```json
{
  "_id": "ObjectId",
  "user_id": "ObjectId",
  "zone_id": "ObjectId (ref: zones)",
  "name": "string (e.g. '钢琴', 'Python')",
  "variant": {
    "species": "string (e.g. 'bamboo' | 'pine' | 'mulberry')",
    "color_hex": "string (e.g. '#5E8C4A')",
    "display_name": "string (e.g. '青竹')"
  },
  "created_at": "datetime"
}
```

**Indexes**: `user_id` · `(user_id, zone_id)` · `(user_id, name)` unique compound

**Note**: `count` is NOT stored here. It is always computed by aggregating `growth_events`. This prevents count drift from partial writes.

---

### 4. `growth_events`

One document per confirmed diary × growth_item pair. Aggregating these gives the count for any item.

```json
{
  "_id": "ObjectId",
  "user_id": "ObjectId",
  "item_id": "ObjectId (ref: growth_items)",
  "tier3_name": "string | null (e.g. '异步编程')",
  "note": "string | null (AI-extracted from raw_mention, e.g. '编出第一个异步函数')",
  "entry_date": "string (YYYY-MM-DD — the diary date, not submission date)",
  "created_at": "datetime (when user confirmed)"
}
```

**Indexes**: `user_id` · `(user_id, item_id)` · `(user_id, entry_date)`

**Count query** (used by `/garden/state` and `/diary/confirm` delta):
```js
db.growth_events.aggregate([
  { $match: { user_id: userId } },
  { $group: { _id: "$item_id", count: { $sum: 1 } } }
])
```

**Dedup rule**: same `(user_id, item_id, entry_date)` combination is rejected with `409 ALREADY_CONFIRMED`. Enforced by unique compound index.

**Unique index**: `(user_id, item_id, entry_date)` — prevents same diary entry counting twice for the same skill.

---

### 5. `ai_usage` (cost monitoring)

```json
{
  "_id": "ObjectId",
  "user_id": "ObjectId",
  "model": "string (deepseek-chat | gpt-4o)",
  "tokens_in": "int",
  "tokens_out": "int",
  "latency_ms": "int",
  "success": "bool",
  "entry_date": "string (YYYY-MM-DD)",
  "created_at": "datetime"
}
```

**Indexes**: `user_id` · `created_at` (for monthly cost rollup)

---

## Data Relationships

```
users (1) ──── (many) zones
users (1) ──── (many) growth_items
zones (1) ──── (many) growth_items
growth_items (1) ──── (many) growth_events
users (1) ──── (many) growth_events
users (1) ──── (many) ai_usage
```

---

## Garden State Computation

`GET /garden/state` builds its response by:

```
1. Fetch all zones for user_id
2. Fetch all growth_items for user_id
3. Aggregate growth_events → count per item_id
4. Join: zones → items (filtered by zone_id) → attach count
5. Return zones array with nested items
```

This is a read-heavy operation run once per session. Acceptable for MVP on 2GB ECS.

---

## Backup

Daily cron at 03:00 UTC:
```bash
mongodump --uri="mongodb://localhost:27017/growth_garden" \
  --out=/tmp/backup/$(date +%Y%m%d)
ossutil cp /tmp/backup/ oss://growth-garden-backup/ --recursive
```

**Mandatory**: verify restore once before production launch.

---

## What is NOT in MVP schema

- Friend/social collections
- Asset definitions collection (species list hardcoded in server config for MVP)
- Zone configuration history
- Notification system

These are additive — adding them later does not require changing existing collections.
