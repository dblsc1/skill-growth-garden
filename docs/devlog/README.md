# devlog/

每个任务一篇，由干活的 worker 在交付前写。文件名 `YYYY-MM-DD-<slug>.md`。

模板（重点是 **Why**，代码说明"做了什么"，devlog 说明"为什么"）：

```markdown
# YYYY-MM-DD — <任务标题>

## What
做了什么。

## Why
为什么这么做（重点）。

## Decisions (ADR-style)
- 关键技术选择 + 取舍理由

## Contract impact
- 无 / 新增字段（additive）/ 破坏性变更（需仲裁者审）

## Tests
- 单元 / E2E 覆盖情况

## Agent
worker=<codex|claude-code>, reviewer=<...>
```
