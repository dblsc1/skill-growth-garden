# ADR 0001 — 日记正文不上服务器

- 状态: Accepted
- 日期: 2026-06-19

## Context

Growth Garden 从用户日记中提炼成长技能。日记正文高度隐私。

## Decision

日记正文**永不落服务器**：
- 正文留在浏览器本地（Godot `user://` / IndexedDB）
- 提炼时正文只发给 DeepSeek/GPT 做抽取，抽取结果（三层技能 + note）才回传
- 服务器只存 `growth_events` 等元数据，绝不存原文，绝不写日志

## Consequences

- 后端任何日志/DB 字段/外部调用都不得出现日记正文（仅 DeepSeek/GPT 抽取除外）
- 渲染走本地优先：Godot 从本地缓存渲染，服务端只传 JSON 计数
- 换设备/清缓存会丢失历史正文 —— 可接受的隐私换便利权衡

## Reference

- `contracts/db_schema.md`、`docs/architecture/` 中的隐私规则
