# Vibecoding 架构笔记 — Growth Garden

用 AI agent 协同开发 Growth Garden 的边界设计、工具选型和纪律规范。

**项目栈**: Godot 4 (GDScript) + Python FastAPI + MongoDB + LangGraph 仲裁者

## 文件索引

| 文件 | 内容 |
|---|---|
| [01-架构选型-langgraph.md](01-架构选型-langgraph.md) | 为什么用 LangGraph、hub-and-spoke 拓扑、灵活分工、三级测试、State 设计 |
| [02-monorepo-文档-注释规范.md](02-monorepo-文档-注释规范.md) | 目录结构、契约层(contracts/)、CLAUDE.md 规范、渐进式严格度 |
| [03-硬边界-沙箱-CI.md](03-硬边界-沙箱-CI.md) | 软约束 vs 硬边界、Docker 沙箱、CI 死闸、多 agent 权限拆分 |
| [04-硬件与资源.md](04-硬件与资源.md) | 内存预算、并发限制、Docker 清理习惯 |
| [05-AI工作留痕-文档管理.md](05-AI工作留痕-文档管理.md) | commit 规范、devlog/ADR、PIPELINE_LOG、留痕义务 |
| **docker/** | Docker 构建文件、各角色启动脚本、docker-compose.dev.yml |
| **claude-md/** | 各角色的 CLAUDE.md / AGENTS.md 模板(复制到实际项目使用) |
| **orchestrator/** | LangGraph 仲裁者源码(graph.py) |

## 一句话总纲

> **Docker 卷边界(互相失明) + contracts/ 只读共享(唯一协作通道) + 仲裁者 AI 中心调度(灵活分工、独占 push)** —— 三层保证各 agent 各写各的、仲裁者协调与最终把关、你只在 escalate 时介入。

## 角色全景

```
你 ── 对话 ──> 仲裁者 AI (HUB, graph.py 节点)
                 │ 每步回到 HUB，灵活派发，独占起服务/联调/push
   ┌─────────────┼──────────────┬───────────────┐
   ↓             ↓              ↓               ↓
后端组         前端组         测试组          仲裁者自己
worker+reviewer worker+reviewer backend-test    integrate(起服务冒烟)
(Codex/CC互换)  (Codex/CC互换)  frontend-test   push(唯一入口)
backend/ rw     godot/ rw      tests/ rw         git push
contracts/ ro   contracts/ ro  contracts/ ro
✗看不到godot     ✗看不到backend ✗看不到任何源码
```

热备份：每组都有 Codex + Claude Code 两个 agent，身份(写/审)由仲裁者每任务灵活决定。

## 项目结构(实际 repo)

```
growth-garden/
├── CLAUDE.md                  ← claude-md/root-CLAUDE.md
├── contracts/                 ← 唯一共享层(所有 agent 只读)
│   ├── openapi.json           ← FastAPI 自动生成
│   └── api_types.ts           ← make sync-contracts 自动生成
├── backend/
│   ├── CLAUDE.md              ← claude-md/backend-CLAUDE.md
│   └── ...                    ← FastAPI 代码 + 单元测试(worker 自测)
├── godot/
│   ├── CLAUDE.md              ← claude-md/frontend-CLAUDE.md
│   └── ...                    ← Godot 4 代码 + GUT 单测(worker 自测)
├── tests/
│   ├── backend/CLAUDE.md      ← claude-md/backend-test-CLAUDE.md  (API 黑盒)
│   └── frontend/CLAUDE.md     ← claude-md/frontend-test-CLAUDE.md (playwright E2E)
├── .github/workflows/
│   ├── ci-backend.yml         ← backend-test 写
│   └── ci-frontend.yml        ← frontend-test 写
├── docs/
│   ├── PIPELINE_LOG.md        ← 仲裁者自动维护
│   └── devlog/                ← 每任务一篇(worker 写)
└── orchestrator/
    ├── graph.py               ← orchestrator/graph.py
    └── requirements.txt        # langgraph, langgraph-checkpoint-sqlite, anthropic
```

> 每个 `CLAUDE.md` 旁都放一份内容相同的 `AGENTS.md`(给 Codex 用)。

## 快速启动(开发流)

```bash
# 1. 构建镜像(一次)
docker build -f docker/Dockerfile.backend  -t growth-garden-backend  .
docker build -f docker/Dockerfile.frontend -t growth-garden-frontend .
docker build -f docker/Dockerfile.test     -t growth-garden-test     .

# 2. 启动仲裁者，它自动分配并驱动整个流程
cd orchestrator && python graph.py "实现 /diary/extract 端点"

# 3. 仲裁者打印 "Launch in a new terminal: AGENT=claude-code bash docker/run-backend-worker.sh"
#    → 照做，启动对应 agent；agent 完成后写状态文件，控制权自动回到仲裁者

# 4. 只有 escalate 时才需要你介入（仲裁者 interrupt 并说明原因）
```

## Agent 角色 & 输出文件

| 角色 | 镜像 | 代码挂载 | 输出文件 |
|---|---|---|---|
| 后端 worker | backend | `backend/` rw + `contracts/` ro | `backend/.agent_status.json` |
| 后端 reviewer | backend | `backend/` **ro** + `contracts/` ro | `.review_output/backend.json` |
| 前端 worker | frontend | `godot/` rw + `contracts/` ro | `godot/.agent_status.json` |
| 前端 reviewer | frontend | `godot/` **ro** + `contracts/` ro | `.review_output/frontend.json` |
| 后端 test | test | `tests/backend/` rw + `contracts/` ro | `.test_output/backend.json` |
| 前端 test | test | `tests/frontend/` rw + `contracts/` ro | `.test_output/frontend.json` |
| 仲裁者 | — | 起服务/联调/push(整仓) | `docs/PIPELINE_LOG.md` |

reviewer / test 的代码目录挂载为 `:ro` —— OS 级别物理防写，不靠 agent 自律。
test 工程师**完全看不到源码**，纯黑盒，只看 contracts + 跑起来的服务。

## 三级测试

| Tier | 内容 | 工具 | 负责人 |
|---|---|---|---|
| 1 单元 | 贴着代码的单测 | pytest / GUT | worker 自测 |
| 2 E2E | 黑盒集成 | pytest+httpx(后端) / playwright(前端) | test 工程师 |
| 3 CI | push 触发跑 1+2 | github actions | test 工程师 |

## 沙箱边界示意

```
后端容器          前端容器          测试容器(后端/前端各一)
┌────────────┐   ┌────────────┐   ┌──────────────────────┐
│backend/ rw │   │godot/   rw │   │tests/<side>/ rw       │
│contracts ro│   │contracts ro│   │contracts/ ro          │
│✗ godot     │   │✗ backend   │   │✗ backend ✗ godot 源码 │
└────────────┘   └────────────┘   │  只通过网络打服务      │
       ↕ contracts/openapi.json ↕  └──────────────────────┘
              (唯一协作通道)        起服务: docker-compose.dev.yml
```
