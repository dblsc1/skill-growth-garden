# Orchestrator Kickoff — One-Time Bootstrap Brief

> 这是给仲裁者(graph.py 的 arbitrator)的**首次启动**简报。一次性使用。
> 跑通第一个任务后即可忽略本文件；后续每个任务直接用 `python graph.py "<task>"` 描述即可。

---

## 0. 你是谁，现在在哪

你是 **arbitrator**（hub）。仓库 `skill-growth-garden` 是一个**空骨架**：
目录结构、契约占位、CI 骨架、各包 `CLAUDE.md` 都已就位，但**还没有任何产品代码**，除了
`backend/main.py` 里一个 `/api/v1/health` 桩。

当前分支 `feature/feature0`。你拥有唯一 push 权（仅在联调干净后 push 到 `feature/*`）。
没有任何东西被提交过 —— 第一次 push 由你完成。

权威文档（不要重复造，需要时去读）：
- 接口：`contracts/openapi.json`（生成物）、`contracts/API_Spec.md`（语义，人读）
- 数据：`contracts/db_schema.md`
- 你的规则：`orchestrator/CLAUDE.md`
- 各 agent 边界：`backend/CLAUDE.md`、`godot/CLAUDE.md`、`tests/{backend,frontend}/CLAUDE.md`
- 留痕规范：`docs/architecture/05-AI工作留痕-文档管理.md`

## 1. MVP 范围（只做这些，别扩张）

阶段 1 的唯一闭环：
1. 用户注册/登录
2. 写一篇日记 → 后端调 DeepSeek 提炼三层技能 → 返回待确认列表（含 AI 提取的 note）
3. 用户在确认框可编辑 note → 确认 → 写 `growth_events` → 返回 delta
4. Godot 渲染**一个**技能森林(forest)，人物可在其中走动；新增/已有树按 count 生长
5. 点开某棵树看详情（tier3 + note + 日期时间线），可编辑 note
6. 其他三个区域(花丛/鱼塘/星空)拉警戒线占位，不可交互
7. 免费额度：10 篇/月，超限 402

**不做**：好友、语音、小镇内部、其它三区的真实玩法。详见 `docs/architecture` 不存在的部分一律不做。

隐私铁律（ADR-0001）：日记正文**永不**落服务器、不进日志，只发给 DeepSeek/GPT 抽取。

## 2. 建议的任务顺序（后端先，契约先稳）

你每次只接一个 task。建议按此序，每完成一个再启动下一个：

| # | task 描述（喂给 `python graph.py`） | 端 | 备注 |
|---|---|---|---|
| 1 | `搭建后端骨架：config、db/mongo 连接、/auth/register /auth/login，写单测` | backend | 复杂 → claude-code |
| 2 | `实现 /diary/extract：调 DeepSeek 提炼三层技能+note，不写库；GPT 兜底` | backend | 复杂；改契约要审 |
| 3 | `实现 /diary/confirm 与 /garden/state 与 PATCH /garden/event/:id` | backend | count 用聚合，勿存 |
| 4 | `后端 API 黑盒集成测试 + 完善 ci-backend.yml` | backend-test | 黑盒 |
| 5 | `Godot 骨架：登录场景、ApiClient、GardenState 本地缓存` | frontend | 复杂 |
| 6 | `花园世界：forest 区 + 人物行走 + 三个占位区警戒线` | frontend | 数据驱动 asset_type |
| 7 | `日记输入面板 + 确认框(可编辑note) + 树木生长 + 详情面板` | frontend | UX 重点 |
| 8 | `Playwright E2E 五大流程 + 完善 ci-frontend.yml` | frontend-test | 黑盒 |

每个 task 你自行决定 mode（solo/review/compete）和 agent（simple→codex / complex→claude-code）。
契约一旦在任务 1–3 稳定，前端任务才好做 —— 所以严格后端先行。

## 3. 每个任务你要做的事（提醒）

1. `analyze_task`：定 side / mode / agent / 写清 instruction
2. 派 worker；按需派 reviewer（身份可互换）
3. 决定是否需要 E2E（功能可见改动→几乎都要；前端必 Playwright）
4. 测试挂 → 带失败日志回 worker；测试过 → 联调
5. `integrate`：`docker compose -f docker/docker-compose.dev.yml up -d` + 冒烟（先打 `/api/v1/health`）
6. 干净 → `push` 到 `feature/<slug>`，Conventional-Commit，body 写 Why，trailer 记哪个 agent 干的
7. 全程往 `docs/PIPELINE_LOG.md` 追加；worker 交活前写 `docs/devlog/`

## 4. 启动前置（人类先做一次）

```bash
make build-images           # 构建 backend/frontend/test 三个镜像
export ANTHROPIC_API_KEY=... # 仲裁者 + agent 用
export OPENAI_API_KEY=...    # 若用 codex / GPT 兜底
export DEEPSEEK_API_KEY=...  # 提炼用，注入到 compose 的 backend
```

## 5. 第一条命令

```bash
cd orchestrator
python graph.py "搭建后端骨架：config、db/mongo 连接、/auth/register /auth/login，写单测"
```

跑通后删除/归档本文件，之后正常按任务表往下推进。
