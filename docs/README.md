# Skill Growth Garden

写日记 → AI 提炼成长技能 → 像素风 2.5D 花园生长。Godot 4 + FastAPI + MongoDB。

## 目录结构

```
├── CLAUDE.md            # 根：项目总览 + 硬规则（所有 agent 读）
├── contracts/           # 唯一共享契约层（所有 agent 只读）
├── backend/             # FastAPI 服务端（后端 agent 读写）
├── godot/               # Godot 4 客户端（前端 agent 读写）
├── tests/
│   ├── backend/         # API 黑盒集成测试（后端 test 工程师）
│   └── frontend/        # Playwright E2E（前端 test 工程师）
├── .github/workflows/   # ci-backend.yml + ci-frontend.yml
├── orchestrator/        # 宿主机裁决者（LangGraph，建设中）
├── docker/              # agent 沙箱镜像 + compose（容器内跑 agent-runner）
└── docs/
    ├── PIPELINE_LOG.md  # 仲裁者调度审计
    ├── devlog/          # 每任务一篇决策记录
    ├── adr/             # 重大架构决策
    └── architecture/    # vibecoding 架构笔记
```

## 开发流（多 agent 容器编排）

```bash
make build-images                                       # 构建 backend/frontend/tester 容器
docker compose -f docker/docker-compose.agents.yml up -d   # 拉起三个 agent 容器
# 宿主机裁决者（orchestrator/，建设中）发任务给容器、审批敏感操作、路由前后端、
# 联测通过后跑 GitHub Actions 云端 CI，绿了才 push 到 feature/*。
# 改 contract 这类大改 → 裁决者写建议书，你（人）批准后才动。
```

细节见 `docs/architecture/README.md` 顶部「现行设计修正」与各包的 `CLAUDE.md`。

## 分支规范

见 `CONTRIBUTING.md`。main / develop 受保护，只走 PR。仲裁者 push 到 `feature/*`。
