"""runner.py — 跑在【每个 worker 容器内】的通用 agent runner。

一个容器 = 一个角色(backend / frontend / tester)。容器只挂载它该看的目录，
所以"看不到别人代码"在 OS 层就成立。本文件把这些 SDK 机制全装上：

  ① system_prompt   → 角色/提示词(常驻)
  ② setting_sources → 让它自动读自己目录的 CLAUDE.md
  ③ add_dirs        → 让它能读 contracts/ 和 docs/(只读)
  ④ 初始命令        → 宿主机 POST /task 进来的任务
  ⑤ can_use_tool    → 敏感工具回调宿主机裁决者/人类审批(见 gate.py)
  ⑥ hooks.PreToolUse→ 每个工具调用留痕(见 audit.py)

宿主机的裁决者通过 HTTP 跟本容器通信：
    POST /task   {"task": "..."}   → 跑完返回 {"report": "..."}
    GET  /health                   → 存活探测
"""

import os
import asyncio
from aiohttp import web

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    TextBlock,
    ResultMessage,
    HookMatcher,
)

from gate import make_gate
from audit import make_audit_hook

# ── 从环境变量读本容器的身份（compose 里按角色注入）──────────────
AGENT_NAME = os.environ["AGENT_NAME"]                 # backend / frontend / tester
AGENT_CWD = os.environ["AGENT_CWD"]                   # 如 /workspace/backend
ALLOWED_TOOLS = os.environ.get("ALLOWED_TOOLS", "Read,Glob,Grep").split(",")
ADD_DIRS = [d for d in os.environ.get("ADD_DIRS", "").split(",") if d]
ROLE_BRIEF = os.environ.get("ROLE_BRIEF", "")         # 角色说明，compose 里写
ARBITRATOR_URL = os.environ.get("ARBITRATOR_URL", "")  # 宿主机审批端点，gate 回调用

# Pro 订阅：容器内绝不能有 API key，强制走挂进来的 ~/.claude 登录态
os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)


def build_options() -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        cwd=AGENT_CWD,
        # ① 角色：保留 Claude Code 本体能力，追加本角色的硬规则
        system_prompt={
            "type": "preset",
            "preset": "claude_code",
            "append": (
                f"{ROLE_BRIEF}\n\n"
                "通用铁律：开工前先读你目录下的 CLAUDE.md 和 contracts/API_Spec.md。"
                "代码要低耦合高内聚、按功能分多文件、禁止超大文件。"
                "每完成一件事，更新你目录下 docs/ 的 dev-log.md 与 structure.md(留痕)。"
                "全局 docs/ 只读。越权/git/改契约等敏感操作会被审批闸拦截。"
            ),
        },
        # ② 自动加载本目录的 CLAUDE.md（SDK 默认不读，必须显式开）
        setting_sources=["project"],
        # ③ 让它能访问只读的 contracts/ 和 docs/
        add_dirs=ADD_DIRS,
        allowed_tools=ALLOWED_TOOLS,
        # ⑤ 敏感工具审批闸（越界/git/契约 → 回调宿主机）
        can_use_tool=make_gate(AGENT_NAME, AGENT_CWD, ARBITRATOR_URL),
        # ⑥ 留痕：每次工具调用前记一行账，写进本目录 docs/audit.log
        hooks={"PreToolUse": [HookMatcher(hooks=[make_audit_hook(AGENT_NAME, AGENT_CWD)])]},
        permission_mode="default",   # 配合 can_use_tool 生效；不是 bypass
    )


class Runner:
    """持有一个常驻会话，宿主机每次 POST /task 就在同一会话里继续（有记忆）。"""

    def __init__(self):
        self.client: ClaudeSDKClient | None = None
        self.lock = asyncio.Lock()   # 同一容器同一时刻只处理一个任务

    async def start(self):
        self.client = ClaudeSDKClient(options=build_options())
        await self.client.connect()

    async def run_task(self, task: str) -> str:
        async with self.lock:
            await self.client.query(task)
            final = ""
            async for m in self.client.receive_response():
                if isinstance(m, AssistantMessage):
                    for b in m.content:
                        if isinstance(b, TextBlock):
                            print(b.text, end="", flush=True)
                elif isinstance(m, ResultMessage):
                    final = m.result or ""
            print(flush=True)
            return final


RUNNER = Runner()


async def handle_task(request: web.Request) -> web.Response:
    body = await request.json()
    task = body.get("task", "")
    if not task:
        return web.json_response({"error": "empty task"}, status=400)
    report = await RUNNER.run_task(task)
    return web.json_response({"agent": AGENT_NAME, "report": report})


async def handle_health(_request: web.Request) -> web.Response:
    return web.json_response({"agent": AGENT_NAME, "status": "ok"})


async def on_startup(_app):
    await RUNNER.start()
    print(f"[{AGENT_NAME}] runner ready, cwd={AGENT_CWD}, tools={ALLOWED_TOOLS}", flush=True)


def main():
    app = web.Application()
    app.router.add_post("/task", handle_task)
    app.router.add_get("/health", handle_health)
    app.on_startup.append(on_startup)
    web.run_app(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))


if __name__ == "__main__":
    main()
