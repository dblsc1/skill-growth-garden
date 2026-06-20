"""gate.py — can_use_tool 审批闸。worker 每次用工具前先过这里。

分级：
  safe      自己目录内的读写、跑测试        → 直接放行
  contract  动 contracts/                  → 回调宿主机，宿主机再升级给【人类】批(大改)
  sensitive git / 跨出自己目录 / 删整目录    → 回调宿主机【裁决者】批
  deny      明显越界                        → 直接拒

注意：因为容器只挂载了自己该看的目录，很多越权在 OS 层已经不可能；
这道闸是【第二层】，兜住容器里仍够得着的敏感操作（主要是 git 和 contracts）。
"""

import os
import aiohttp
from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny

# 这些工具一旦碰，需要审批
WRITE_TOOLS = {"Write", "Edit", "NotebookEdit"}
EXEC_TOOLS = {"Bash"}

# Bash 命令里出现这些关键字 = 敏感，必须裁决者批
SENSITIVE_CMDS = ("git push", "git commit", "git remote", "git reset", "rm -rf", "curl", "wget", "pip install", "npm install")


def _path_in(path: str, root: str) -> bool:
    try:
        return os.path.realpath(path).startswith(os.path.realpath(root))
    except Exception:
        return False


def _classify(tool_name: str, tool_input: dict, agent_cwd: str) -> str:
    # 改 contracts/ → contract（最高级，要人批）
    target = tool_input.get("file_path") or tool_input.get("path") or ""
    if "/contracts/" in target or target.endswith("contracts"):
        return "contract"

    if tool_name in WRITE_TOOLS:
        # 写自己目录 = safe；写到自己目录外 = sensitive
        return "safe" if _path_in(target, agent_cwd) else "sensitive"

    if tool_name in EXEC_TOOLS:
        cmd = (tool_input.get("command") or "").lower()
        if "contracts/" in cmd and (">" in cmd or "tee" in cmd or "cp " in cmd or "mv " in cmd):
            return "contract"
        if any(k in cmd for k in SENSITIVE_CMDS):
            return "sensitive"
        return "safe"   # 普通命令（跑测试等）

    # 读类工具：能读到的都是挂载允许的目录，放行
    return "safe"


async def _ask_host(arbitrator_url: str, payload: dict) -> tuple[bool, str]:
    """回调宿主机审批端点。宿主机内部决定是裁决者还是人类来批。"""
    if not arbitrator_url:
        return False, "未配置 ARBITRATOR_URL，默认拒绝敏感操作"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(f"{arbitrator_url}/approve", json=payload, timeout=600) as r:
                data = await r.json()
                return bool(data.get("allow")), data.get("reason", "")
    except Exception as e:
        return False, f"审批回调失败，保守拒绝：{e}"


def make_gate(agent_name: str, agent_cwd: str, arbitrator_url: str):
    async def gate(tool_name: str, tool_input: dict, context):
        level = _classify(tool_name, tool_input, agent_cwd)

        if level == "safe":
            return PermissionResultAllow()

        # contract / sensitive 都回调宿主机；level 让宿主机知道要不要升级给人类
        allow, reason = await _ask_host(arbitrator_url, {
            "agent": agent_name,
            "level": level,                 # "contract" → 宿主机升级给人类；"sensitive" → 裁决者
            "tool": tool_name,
            "input": tool_input,
        })
        if allow:
            return PermissionResultAllow()
        return PermissionResultDeny(message=f"[{level}] 审批未通过：{reason}")

    return gate
