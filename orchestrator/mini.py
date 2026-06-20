"""mini.py — 最小可行编排器：4 个 Claude agent（全吃 Pro 订阅）+ 代码审查环 + 黑盒联测环 + git push。

这是 StudyLanggarph/ccworker.py 的放大版：
  - 1 个 worker → 4 个：backend / frontend / arbitrator(裁决者) / tester(测试工程师)
  - 两条【条件边循环】：
      ① 代码审查环：裁决者审代码，打回 → 回 build 重做
      ② 黑盒联测环：测试工程师联测，挂了 → 裁决者 triage 定位 → 派 debug → 回 build
  - 最后裁决者独占 git push

砍掉的重型东西（以后加都是局部改动）：Docker 硬隔离、Codex 备份、reviewer 备份、compete。
注意：测试工程师"看不到前后端源码"在本版只是 brief 软约束；硬隔离需 Docker（后续升级）。

跑法：
    cd skill-growth-garden/orchestrator
    python mini.py "搭建后端骨架：config、db/mongo 连接封装，写能离线跑的单测"
"""

import os
import sys
import asyncio
from typing import TypedDict, Optional

from langgraph.graph import StateGraph, START, END
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    TextBlock,
    ResultMessage,
)

os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MAX_BUILD_ATTEMPTS = 2   # 单轮代码审查最多打回几次
MAX_DEBUG_ROUNDS = 2     # 联测挂了最多 debug 几轮
PUSH_ENABLED = False     # 安全阀：True 才真 git push（先 False，跑通逻辑再开）


# ──────────────────────────────────────────────────────────────
# 1. 通用 worker（同 ccworker.py，多带一段开场身份说明）
# ──────────────────────────────────────────────────────────────
class ClaudeWorker:
    def __init__(self, name, cwd, allowed_tools, brief, permission_mode="bypassPermissions"):
        self.name = name
        self.brief = brief
        self.options = ClaudeAgentOptions(cwd=cwd, allowed_tools=allowed_tools, permission_mode=permission_mode)
        self.client: Optional[ClaudeSDKClient] = None
        self._opened = False

    async def start(self):
        self.client = ClaudeSDKClient(options=self.options)
        await self.client.connect()

    async def send(self, task: str) -> str:
        msg = task if self._opened else f"{self.brief}\n\n---\n\n{task}"
        self._opened = True
        print(f"\n========== [{self.name}] 收到任务 ==========")
        await self.client.query(msg)
        final = ""
        async for m in self.client.receive_response():
            if isinstance(m, AssistantMessage):
                for block in m.content:
                    if isinstance(block, TextBlock):
                        print(block.text, end="", flush=True)
            elif isinstance(m, ResultMessage):
                final = m.result or ""
        print(f"\n---------- [{self.name}] 交活 ----------\n")
        return final

    async def close(self):
        if self.client:
            await self.client.disconnect()


# ──────────────────────────────────────────────────────────────
# 2. 四个 agent（活资源放图外）
# ──────────────────────────────────────────────────────────────
WORKERS: dict[str, ClaudeWorker] = {}


def build_workers():
    WORKERS["backend"] = ClaudeWorker(
        name="backend", cwd=REPO,
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        brief=(
            "你是【后端开发 agent】。开工前先读 `backend/CLAUDE.md`、`contracts/API_Spec.md`、"
            "`contracts/db_schema.md`，严格按契约写。只准改 `backend/`，别碰 `godot/`、`contracts/`、`tests/`。"
            "隐私铁律：日记正文永不落库、不进日志。交活前自己把单测跑过。"
        ),
    )
    WORKERS["frontend"] = ClaudeWorker(
        name="frontend", cwd=REPO,
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        brief=(
            "你是【前端(Godot)开发 agent】。开工前先读 `godot/CLAUDE.md`、`contracts/API_Spec.md`。"
            "只准改 `godot/`。"
        ),
    )
    WORKERS["arbitrator"] = ClaudeWorker(
        name="arbitrator", cwd=REPO,
        allowed_tools=["Read", "Glob", "Grep", "Bash"],  # 只读+能跑测试/ git，但无 Write/Edit
        brief=(
            "你是【裁决者】。你不写代码、不改代码。你的活有三种，我每次会告诉你这次干哪种：\n"
            "(A) 审代码：审 worker 产出是否符合 `contracts/` 契约和对应 CLAUDE.md，并跑测试验证。"
            "最后一行只输出 `PASS: 理由` 或 `FAIL: 哪里不行+怎么改`。\n"
            "(B) 定位 bug(triage)：给你联测失败日志，你判断是前端还是后端的问题、根因是什么、"
            "该派什么 debug 任务。最后一行只输出 `SIDE: backend|frontend` 然后另起一行 `FIX: 具体整改指令`。\n"
            "(C) 终检+发布：跑一遍冒烟，没问题就 git push 到 feature/* 分支（只有你有 push 权）。"
        ),
    )
    WORKERS["tester"] = ClaudeWorker(
        name="tester", cwd=os.path.join(REPO, "tests"),
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        brief=(
            "你是【测试工程师】，做黑盒联测。**严禁打开 / 阅读 `backend/`、`godot/` 的源码**——"
            "你只通过契约 `contracts/API_Spec.md` 和【运行中的服务】来测（HTTP 打后端、Playwright 打前端）。"
            "测试代码写在 `tests/` 下。先读 `tests/backend/CLAUDE.md`、`tests/frontend/CLAUDE.md`。"
            "跑完最后一行只输出 `TEST_PASS: 概述` 或 `TEST_FAIL: 失败现象+复现+期望 vs 实际`。"
        ),
    )


def _last_tagged_line(text: str, *tags: str):
    """从底往上找以某 tag 开头的行，返回 (tag, 该行去掉 tag 后的内容)。"""
    for line in reversed(text.strip().splitlines()):
        s = line.strip()
        for t in tags:
            if s.upper().startswith(t.upper()):
                return t, s[len(t):].lstrip(": ").strip()
    return None, ""


# ──────────────────────────────────────────────────────────────
# 3. State
# ──────────────────────────────────────────────────────────────
class DevState(TypedDict):
    side: str            # 当前派给谁：backend / frontend
    task: str            # 原始任务
    feedback: str        # 代码审查 / debug 的整改意见（重做时带上）
    build_report: str
    verdict: str         # 代码审查结果 pass/fail
    attempts: int        # 代码审查已重做次数
    test_report: str
    test_verdict: str    # 联测结果 pass/fail
    debug_round: int     # 联测挂了已 debug 几轮
    pushed: bool


# ──────────────────────────────────────────────────────────────
# 4. 节点
# ──────────────────────────────────────────────────────────────
async def build(state: DevState) -> DevState:
    worker = WORKERS[state["side"]]
    task = state["task"]
    if state.get("feedback"):
        task = (f"上一版被打回，请按意见整改后重新交活。\n\n意见：\n{state['feedback']}\n\n原任务：\n{state['task']}")
    report = await worker.send(task)
    return {"build_report": report, "feedback": "", "attempts": state["attempts"] + 1}


async def review(state: DevState) -> DevState:
    out = await WORKERS["arbitrator"].send(
        f"【任务A 审代码】worker 完成了：{state['task']}\n\n它的报告：\n{state['build_report']}\n\n"
        f"请审查 `{state['side']}/` 的实际改动并跑测试，最后一行给 PASS/FAIL。"
    )
    tag, rest = _last_tagged_line(out, "PASS", "FAIL")
    if tag == "PASS":
        return {"verdict": "pass", "feedback": ""}
    return {"verdict": "fail", "feedback": rest or out}


async def integ_test(state: DevState) -> DevState:
    out = await WORKERS["tester"].send(
        f"对当前后端做黑盒联测（写/补 `tests/` 下测试，起服务，按 `contracts/API_Spec.md` 验证）。"
        f"本次重点覆盖刚交付的功能：{state['task']}\n最后一行给 TEST_PASS / TEST_FAIL。"
    )
    tag, rest = _last_tagged_line(out, "TEST_PASS", "TEST_FAIL")
    return {"test_report": out, "test_verdict": "pass" if tag == "TEST_PASS" else "fail"}


async def triage(state: DevState) -> DevState:
    """联测挂了：裁决者定位根因 + 派 debug 任务（决定 side 和整改指令）。"""
    out = await WORKERS["arbitrator"].send(
        f"【任务B 定位bug】黑盒联测失败。测试工程师的报告：\n{state['test_report']}\n\n"
        f"请判断是 backend 还是 frontend 的问题、根因、整改指令。"
        f"按格式：`SIDE: backend|frontend` 换行 `FIX: ...`。"
    )
    side_tag, side_val = _last_tagged_line(out, "SIDE")
    _, fix_val = _last_tagged_line(out, "FIX")
    side = "frontend" if side_val.lower().startswith("frontend") else "backend"
    return {
        "side": side,
        "feedback": fix_val or out,
        "attempts": 0,                       # 新一轮代码审查，重置审查计数
        "debug_round": state["debug_round"] + 1,
    }


async def push(state: DevState) -> DevState:
    """终检 + git push（仅裁决者）。"""
    cmd = "git push 到 feature/* 分支" if PUSH_ENABLED else "**只做终检冒烟，不要真 push**（本次 push 关闭）"
    out = await WORKERS["arbitrator"].send(
        f"【任务C 终检+发布】所有测试已绿。请最后跑一遍冒烟检查（先打 `/api/v1/health`）。"
        f"没问题则{cmd}，用 Conventional Commit，body 写清这次做了什么、Why。"
    )
    print(f"\n🚀 终检/发布完成：\n{out[-400:]}")
    return {"pushed": True}


# ──────────────────────────────────────────────────────────────
# 5. 条件边
# ──────────────────────────────────────────────────────────────
def after_review(state: DevState) -> str:
    if state["verdict"] == "pass":
        print(f"\n✅ 代码审查通过（{state['attempts']} 次）→ 进入联测")
        return "to_test"
    if state["attempts"] >= MAX_BUILD_ATTEMPTS:
        print(f"\n⛔ 代码审查 {MAX_BUILD_ATTEMPTS} 次未过，停下交人工。")
        return "give_up"
    print(f"\n🔁 审查打回：{state['feedback'][:80]}...")
    return "retry"


def after_test(state: DevState) -> str:
    if state["test_verdict"] == "pass":
        print("\n✅ 黑盒联测通过 → 终检 + 发布")
        return "to_push"
    if state["debug_round"] >= MAX_DEBUG_ROUNDS:
        print(f"\n⛔ 联测 debug {MAX_DEBUG_ROUNDS} 轮仍挂，停下交人工。")
        return "give_up"
    print("\n🐛 联测失败 → 裁决者定位 + 派 debug")
    return "to_triage"


graph = StateGraph(DevState)
graph.add_node("build", build)
graph.add_node("review", review)
graph.add_node("integ_test", integ_test)
graph.add_node("triage", triage)
graph.add_node("push", push)

graph.add_edge(START, "build")
graph.add_edge("build", "review")
graph.add_conditional_edges("review", after_review,
                            {"retry": "build", "to_test": "integ_test", "give_up": END})
graph.add_conditional_edges("integ_test", after_test,
                            {"to_push": "push", "to_triage": "triage", "give_up": END})
graph.add_edge("triage", "build")   # debug 任务回到 build 重做
graph.add_edge("push", END)
app = graph.compile()


# ──────────────────────────────────────────────────────────────
# 6. 入口
# ──────────────────────────────────────────────────────────────
async def main():
    task = sys.argv[1] if len(sys.argv) > 1 else \
        "搭建后端骨架：config 模块、db/mongo 连接封装，并写一个不依赖真实数据库就能跑的单测"

    build_workers()
    # 本轮起 backend + arbitrator + tester（frontend 先不雇，省额度）
    for name in ("backend", "arbitrator", "tester"):
        await WORKERS[name].start()

    init: DevState = {
        "side": "backend", "task": task, "feedback": "",
        "build_report": "", "verdict": "", "attempts": 0,
        "test_report": "", "test_verdict": "", "debug_round": 0, "pushed": False,
    }
    await app.ainvoke(init, config={"recursion_limit": 40})

    for name in ("backend", "arbitrator", "tester"):
        await WORKERS[name].close()


if __name__ == "__main__":
    asyncio.run(main())
