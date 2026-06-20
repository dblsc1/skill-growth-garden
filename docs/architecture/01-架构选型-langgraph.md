# 架构选型:LangGraph 作为多 agent 开发骨架

## LangGraph 的地基:State + Node + Edge

LangGraph 本质是个**状态机**:
- `State`(TypedDict):贯穿全流程的共享数据
- `Node`:函数,读 State、改 State、返回 dict
- `Edge` / 条件边:控制流转、分支、循环
- `compile` + `stream`:编译成 app 后执行

**核心架构理念:节点内高自主、节点间强管控。**
- 节点**内部**:Codex / Claude Code 在 Docker 沙箱里自主完成任务。
- LangGraph 只负责**串流程、管状态、控分支**。
- **决策**由仲裁者 Claude 节点做，不由 LangGraph 路由函数做。

## LangChain ≠ LangGraph(别混淆)

| | 地基 | 心智模型 | 适合 |
|---|---|---|---|
| **LangChain** | Runnable + LCEL | 流水线,只能往前流 | 直来直去的链:RAG、一次问答 |
| **LangGraph** | State + Node(状态机) | 图,可循环、可回头 | 有环有状态的流程:agent、审批流 |

**不用专门学 LangChain。** LangGraph 节点里需要什么直接调用 anthropic SDK / openai SDK 即可。

## Growth Garden 实际架构（中心调度 Hub-and-Spoke）

仲裁者是**中心枢纽**。每个 agent 步骤结束后，控制权都回到仲裁者，由它决定下一步。
这样 agent 分工是**完全灵活**的——仲裁者每一步自己定。

```
你
 ↕ 对话 / 只在 escalate 时介入
仲裁者 Claude（HUB，LangGraph 节点，调用 Anthropic API）
 │  每步都回到这里，读全部报告 → 决定 next_action
 │  独占权力：起服务、跑联调冒烟、push（其他 agent 都不能 push）
 ↓ 派发到 spoke，spoke 干完回到 HUB
 ├─ run_build       后端/前端 编码（solo / compete / review 灵活）
 ├─ run_test        E2E 测试工程师（后端 API 黑盒 / 前端 playwright）
 ├─ run_integration 仲裁者起服务 + 冒烟检查（最终关）
 └─ run_push        仲裁者提交 + push feature 分支（唯一 push 入口）
```

**灵活分工（仲裁者每个 build 自己选 mode）：**

| mode | 含义 |
|---|---|
| `solo` | 一个 agent 单干，不复查 |
| `review` | 一个写、另一个只读复查（身份可互换，Codex 也能查 Claude Code）|
| `compete` | 两个 agent 各在自己 git 分支干，仲裁者择优 |

简单→Codex，复杂→Claude Code（仲裁者可覆盖）。

**关键规则:**
- 仲裁者只读代码、不写代码、不自己改 bug（改 bug 派给 worker，找 bug 派给 test）
- 审批全部由仲裁者完成，不依赖人工断点（除非 escalate）
- Reviewer / test 的代码目录挂载为 `:ro`，OS 级别物理防写
- test 工程师**看不到源码**，纯黑盒，只看 contracts + 跑起来的服务

## 完整 LangGraph 图（hub-and-spoke）

```
START → analyze_task → arbitrator_dispatch (HUB)
                              │
        ┌─────────┬──────────┼───────────┬──────────┐
        ↓         ↓          ↓           ↓          ↓
   run_build  run_test  run_integration run_push  (escalate/done → END)
        │         │          │           │
        └─────────┴──────────┴───────────┘
                  全部回到 arbitrator_dispatch

HUB 每次决策 next_action ∈ {build, test, integrate, push, escalate, done}
典型路径：
  build(backend) → test(backend API) → [pass] → build(frontend)
  → test(frontend playwright) → [pass] → integrate → [clean] → push → done
  任一 test fail → build(对应端，带失败日志修) → 再 test
```

## 三级测试结构（pytest → playwright → github action）

| Tier | 内容 | 谁负责 |
|---|---|---|
| 1 单元 | 后端 pytest 单测 / 前端 GUT，贴着代码写 | **worker 自测**（仲裁者可不单独派）|
| 2 E2E | 后端 API 黑盒(pytest+httpx) / 前端 playwright 浏览器 | **test 工程师** |
| 3 CI | `.github/workflows/ci-backend.yml` + `ci-frontend.yml`，push 时跑 1+2 | **test 工程师**（前后端各写各的）|

仲裁者负责联调（起服务、冒烟），决定要不要 push。

## State 设计

```python
class DevState(TypedDict):
    task: str
    directive: dict             # 仲裁者给下一个 spoke 的指令(side/mode/agent/instruction)

    backend_status: str         # not_started|built|test_pass|test_fail|approved
    frontend_status: str
    retry_counts: dict          # {"backend_build":1, "frontend_test":0}

    next_action: str            # HUB 决定:build|test|integrate|push|escalate|done
    push_done: bool

    reports: Annotated[list[dict], operator.add]        # worker+reviewer 报告(append-only)
    test_logs: Annotated[list[dict], operator.add]      # 测试日志(保留)
    arbitrator_log: Annotated[list[str], operator.add]  # 调度审计(append-only)
```

`directive` 是 HUB 与 spoke 之间的"工单"：HUB 写好 side/mode/agent/instruction，
spoke 照着启动对应 Docker。所有跨 agent 沟通都走 state（不开额外通道）。

## Agent 完成信号:状态文件协议

Agent 干完活 → 写文件 → LangGraph 轮询检测到 → 控制权回 HUB

| 角色 | 写的文件 | 格式 |
|---|---|---|
| 后端/前端 worker | `backend/.agent_status.json` / `godot/.agent_status.json` | `{"status":"done","summary":"...","contracts_changed":false}` |
| reviewer | `.review_output/{side}.json` | `{"status":"approved","issues":[],"summary":"..."}` |
| test 工程师 | `.test_output/{side}.json` | `{"status":"pass|fail","summary":"...","failures":[...]}` |

## LangGraph 设计建议

**1. HUB 做判断，路由函数只查表**

所有决策在 `arbitrator_dispatch`（HUB）里由 Claude 完成并写进 `next_action`。
路由函数零逻辑，纯查表——这是 hub-and-spoke 的精髓：
```python
def route(state):
    return {
        "build": "run_build", "test": "run_test",
        "integrate": "run_integration", "push": "run_push",
        "escalate": END, "done": END,
    }.get(state["next_action"], END)
```

**2. 每个 spoke 干完都回 HUB**

不要在 spoke 之间连边。所有 spoke 的出边都指向 HUB，HUB 再决定下一步。
这样新增能力（比如加个"安全扫描"spoke）只要加节点 + 在 HUB 的选项里加一项，不动流程图。
```python
for spoke in ["run_build","run_test","run_integration","run_push"]:
    g.add_edge(spoke, "arbitrator_dispatch")
```

**3. `interrupt` 只作为逃生舱**

正常流程不触发。只有 HUB 决定 `escalate` 才触发，把控制权交还给你：
```python
if decision["next_action"] == "escalate":
    interrupt({"message": decision["escalate_message"]})
```

**4. `recursion_limit` 要算够**

hub-and-spoke 每轮 = spoke + 回 HUB = 2 跳。一个完整任务（后端 build→test，前端
build→test，integrate，push）轻松上 15+ 跳，retry 还会叠加。设 `MAX_TOTAL_STEPS=40`：
```python
config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 40}
```

**5. `Annotated[list, operator.add]` 做审计轨迹**

reports / test_logs / arbitrator_log 都用追加语义，绝不能被覆盖——这是留痕和复盘的基础。

**6. retry_counts 防死循环**

HUB 每次派 build/test 给某端就 `retry_counts[f"{side}_{action}"] += 1`。
HUB 读到某项超过阈值（如 3）就应该选 `escalate` 而不是再 retry。阈值判断写在仲裁者 prompt 里。

**7. compete 模式靠 git 分支隔离**

两个 agent 不能同时写同一个 `backend/`。`compete` 时给每个 agent 一个分支（`directive.branches`），
worker 脚本读 `BRANCH` 环境变量各自 checkout，HUB 事后 diff 择优合并。

**8. Thread ID 按任务命名，方便 checkpoint 续跑**

```python
thread_id = f"task-{int(time.time())}"
```

**9. 暂不用 Subgraph / Send**

hub-and-spoke 已经够灵活。等出现"可复用子流程"或"确定可并行的独立任务"再上 Subgraph / Send。

## ⚠️ LangGraph 管不全的部分

- LangGraph 管"仲裁者说做什么、谁来做"
- Docker `:ro` 挂载管"reviewer 物理上不能写代码"
- `CLAUDE.md` / `AGENTS.md` 管"agent 知道自己的边界和输出格式"

**三层缺一个就会漏。** 见 03-硬边界-沙箱-CI.md。

## 要学到什么程度(干中学)

```
阶段1  fake status 文件，把完整图跑通（verify routing）
阶段2  接入真 Docker agent，让节点真正等待状态文件
阶段3  观察仲裁者 Claude 的决策质量，调整 system prompt
阶段4  撞上"看不清流程" → 接 LangSmith traces
阶段5  出现可复用子流程 / 可并行任务 → 上 Subgraph / Send
```
