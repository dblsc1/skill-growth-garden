# Monorepo 架构 / 文档 / 注释规范

前提画像:前端 TS + 后端 Python + 调度 Python | AI 写、人审 | Monorepo | 渐进式。

## 关键矛盾(整个方案围着它转)

> 你跨了语言边界(TS↔Python),又让 AI 写大部分代码。两个最大风险:
> ① 前后端"对不上"(类型漂移);② AI 缺上下文时乱发挥、越界。
> 可塑性/拓展性/健壮性的全部功夫 = 消除这两个风险。

## 1. Monorepo 目录结构

```
platform/
├─ AGENTS.md                 # 给 Codex 的总规约
├─ CLAUDE.md                 # 给 Claude Code 的总规约
├─ README.md                 # 给人:怎么跑起来
├─ docs/
│  ├─ architecture.md        # 一张图 + 模块边界(唯一架构总览)
│  ├─ adr/                   # 架构决策记录 0001-xxx.md
│  └─ glossary.md            # 术语表(统一叫法)
├─ packages/
│  ├─ contracts/             # ★★★ 单一事实源:接口/数据契约
│  ├─ frontend/   (TS)       # React/Next + CLAUDE.md
│  ├─ backend/    (Python)   # FastAPI + CLAUDE.md
│  └─ orchestrator/(Python)  # LangGraph 调度+审批 + CLAUDE.md
├─ pnpm-workspace.yaml       # TS 侧 workspace
└─ Makefile / justfile       # 统一入口:make dev / make check
```

- 三个 package = 边界即文件夹,AI 改哪块就只进哪块,限制爆炸半径。
- 扩建(新游戏/新服务)= 新增一个 package,不动老的 = 拓展性的物理保证。

## 2. ★ 契约层:解决"前后端对不上"(健壮性命根)

让契约只写一次,两边自动同步:
```
FastAPI(Pydantic 模型) ──自动──> /openapi.json ──openapi-typescript──> 前端 TS 类型
```
- 前端调接口类型对不上 → **编译直接报错**,而不是上线才炸。
- AI 改了后端模型却忘改前端 → 立刻红。

落地:`packages/contracts/` 放 `make sync-contracts`(重新生成 TS 类型)。
**别靠 AI 自觉,靠机器卡死边界。** 这一个机制顶 100 条口头规范。

## 3. 文档体系:写成"AI 的喂料"

第一读者是 AI agent。三层:

| 文档 | 位置 | 写给谁 | 内容 |
|---|---|---|---|
| **CLAUDE.md / AGENTS.md** | 每个 package + 顶层 | AI | 包是干嘛、**边界(能碰/不能碰)**、命名约定、跑测试命令、**禁止事项** |
| **architecture.md** | docs/ | 人+AI | 一张图 + 三模块职责和数据流向,1 页 |
| **ADR** | docs/adr/ | 人+未来 | "为什么这么选",每个重大决策一个 5 行小文件 |

局部 CLAUDE.md 示例(backend):
```markdown
# backend / CLAUDE.md
本包:FastAPI 后端,只负责 HTTP 接口 + 业务逻辑。

## 边界(硬规则)
- 数据模型一律用 Pydantic,放 models/。改模型必须跑 make sync-contracts。
- 不准在这里调 LangGraph;调度逻辑属于 orchestrator 包。
- 不准直接写 SQL,统一走 repositories/ 层。

## 约定
- 新接口:路由放 routers/,业务放 services/,一文件一职责。
- 跑检查:make check-backend(lint+类型+测试),提交前必过。

## 禁止
- 不准把密钥写进代码,走 .env。
- 不准删除/重写 migrations/ 历史文件。
```
这份文件 = "规范"和"安全边界"的落地点。审核 = 审 AI 有没有违反 CLAUDE.md。

## 4. 注释规范(AI 时代版)

AI 生成代码最大毛病是注释复述代码。三条:

1. **代码自解释 = 不写注释**(名字取好胜过注释)。
2. **只在"为什么"处写注释**:
   ```python
   # 这里故意不并发:出题接口有速率限制,并发会被封。别"优化"成 asyncio.gather。
   ```
   能阻止 AI 下次"好心"改坏。
3. **公共函数/节点用 docstring 写契约**(输入、输出、副作用):
   ```python
   def grade(state: State) -> dict:
       """批改并更新掌握度。
       读: state.answer, state.current_q
       写: 返回 {"level": 新掌握度} —— 只改 level
       副作用: 无(纯函数,便于重跑)
       """
   ```

口诀:**名字讲 what,注释讲 why,docstring 讲 contract。**

## 5. 渐进式严格度阶梯

| 阶段 | 加什么 | 解决的痛 |
|---|---|---|
| **现在(MVP)** | 目录结构 + 各包 CLAUDE.md + contracts 自动同步 + `make check`(lint+类型) | 边界、前后端对齐——**现在就必须有** |
| 跑通后 | 关键路径写测试(只测核心逻辑) | 防 AI 改坏核心 |
| 多人/多 AI 并行 | CI(push 自动跑)+ PR 模板 | 防脏代码进主干 |
| 项目变大 | ADR 制度化、LangSmith、SqliteSaver | 决策可追溯、流程可调试 |
| 真有性能/可靠性痛 | 性能预算、错误重试策略 | 健壮性收尾 |

**红线:前三样(结构+CLAUDE.md+契约同步)是"现在",返工成本最高。其余撞墙再加。**

## 6. "AI 写、人审"工作流:提交前自检清单

贴进顶层 CLAUDE.md,让 AI 自查后再交:
```
□ 改动只在该包内?没越界碰别的包?
□ 改了数据模型 → 跑了 make sync-contracts?
□ make check 全绿(lint+类型)?
□ 没违反本包 CLAUDE.md 的"禁止"?
□ 注释只写了 why,没复述代码?
□ 没硬编码密钥/路径?
```
你先看它有没有过这 6 条,过了再看业务逻辑,审核负担降一个量级。
