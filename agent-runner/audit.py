"""audit.py — PreToolUse 留痕 hook。每个工具调用前追加一行 JSONL 到本 agent 的 docs/audit.log。

留痕是"给人看 + git 化"的：audit.log 在 agent 自己目录的 docs/ 下，会随代码一起提交。
裁决者审代码时可对照这份操作流水。
"""

import os
import json
import time


def make_audit_hook(agent_name: str, agent_cwd: str):
    log_dir = os.path.join(agent_cwd, "docs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "audit.log")

    async def hook(input_data: dict, tool_use_id, context) -> dict:
        try:
            tool_name = input_data.get("tool_name", "?")
            tool_input = input_data.get("tool_input", {})
            # 只记摘要，别把整段代码灌进日志
            brief = {
                k: (str(v)[:200] + "…" if len(str(v)) > 200 else v)
                for k, v in (tool_input or {}).items()
            }
            line = {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "agent": agent_name,
                "tool": tool_name,
                "input": brief,
                "id": tool_use_id,
            }
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(line, ensure_ascii=False) + "\n")
        except Exception:
            pass  # 留痕失败绝不能挡住正常干活
        return {}  # 空 = 放行，决策交给 can_use_tool

    return hook
