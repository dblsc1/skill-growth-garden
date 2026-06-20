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
├── orchestrator/        # LangGraph 仲裁者（graph.py）
├── docker/              # 各角色沙箱镜像 + 启动脚本 + compose
└── docs/
    ├── PIPELINE_LOG.md  # 仲裁者调度审计
    ├── devlog/          # 每任务一篇决策记录
    ├── adr/             # 重大架构决策
    └── architecture/    # vibecoding 架构笔记
```

## 开发流（vibe coding）

```bash
make build-images                    # 一次：构建三个 agent 镜像
cd orchestrator && python graph.py "实现 /diary/extract 端点"
# 仲裁者灵活分配 worker/reviewer/test，独占起服务+联调+push
# 你只在 escalate 时介入
```

细节见 `docs/architecture/README.md` 与各包的 `CLAUDE.md`。

## 分支规范

见 `CONTRIBUTING.md`。main / develop 受保护，只走 PR。仲裁者 push 到 `feature/*`。
