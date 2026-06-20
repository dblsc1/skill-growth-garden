"""
Growth Garden — LangGraph Arbitrator (Hub-and-Spoke)

Topology:
  START → analyze_task → arbitrator_dispatch ⇄ { spoke nodes } → END

  arbitrator_dispatch is the HUB. After every spoke finishes, control returns
  to the hub. The arbitrator Claude reads all reports and decides the next
  action. This makes agent assignment fully flexible — the arbitrator decides
  per step:
    - who builds (codex / claude-code)
    - solo, or two-compete (pick best), or one-builds-one-reviews
    - whether reviewer is needed at all
    - when to run E2E tests (workers do their own unit tests inline)
    - whether the build is good enough to integrate & push

  ONLY the arbitrator (push spoke) has git push rights.
  Test engineers and workers never push.

Spokes (each returns to the hub):
  run_build       — build/fix code (backend or frontend), flexible mode
  run_test        — E2E test engineer writes+runs tests (backend API / frontend playwright)
  run_integration — arbitrator starts services via docker-compose, final smoke check
  run_push        — arbitrator commits + pushes to feature branch (sole push authority)

Communication: all cross-agent info flows through DevState (Q2 = state).
Test logs are kept in state["test_logs"] and mirrored to docs/PIPELINE_LOG.md.

Run: python graph.py "implement /diary/extract endpoint"
"""

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Annotated, TypedDict
import operator

import anthropic
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

# ── Config ─────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", Path(__file__).parent.parent))
ARBITRATOR_MODEL = "claude-opus-4-8"
MAX_TOTAL_STEPS = 40          # recursion ceiling for the hub loop
POLL_INTERVAL = 15            # seconds between status-file checks
POLL_TIMEOUT = 1800           # 30 min max wait per agent

client = anthropic.Anthropic()


# ── State ──────────────────────────────────────────────────────────────────────

class DevState(TypedDict):
    task: str

    # The arbitrator's directive for the NEXT spoke it routes to.
    # Shape depends on next_action; see analyze/dispatch for the schema.
    directive: dict

    # Coarse status per side: not_started | built | test_pass | test_fail | approved
    backend_status: str
    frontend_status: str

    # Per-action retry counters, e.g. {"backend_build": 1, "frontend_test": 0}
    retry_counts: dict

    next_action: str   # set by the hub: build|test|integrate|push|escalate|done

    push_done: bool

    # Append-only audit channels (Q2: communication via state)
    reports: Annotated[list[dict], operator.add]      # worker + reviewer reports
    test_logs: Annotated[list[dict], operator.add]    # kept test run logs
    arbitrator_log: Annotated[list[str], operator.add]


# ── Arbitrator LLM ───────────────────────────────────────────────────────────

ARBITRATOR_SYSTEM = """You are the ARBITRATOR for the Growth Garden multi-agent dev pipeline.

You are the hub. After each agent step you decide what happens next.
You NEVER write code. You read reports/logs, decide, and route.

Your powers (decide freely per task):
- Assign each build to "codex" (simple) or "claude-code" (complex)
- Choose a build MODE:
    "solo"    — one agent does it, no review
    "compete" — two agents each build on their own git branch; you pick the better one
    "review"  — one builds, the OTHER reviews (read-only); roles are not fixed
- Decide whether E2E tests run now, or later, or are skipped for a trivial change
  (workers run their OWN unit tests inline — you only schedule the playwright/API E2E tier)
- When tests fail: route the failure back to the build agents (with the failure log)
- When tests pass: move toward integration
- Run integration yourself (start services, smoke check). If clean → push. If not → send to test.
- ONLY you push to git, and only after integration is clean.
- Escalate to the human when stuck (3+ failed retries, security issue, or ambiguous contract change)

Stack: Godot 4 (frontend) + Python FastAPI (backend) + MongoDB + DeepSeek.
Rule: backend stabilizes before frontend adapts. Diary text never logged/stored server-side.

Respond ONLY in JSON. No prose outside the JSON block.
"""

def call_arbitrator(prompt: str) -> dict:
    resp = client.messages.create(
        model=ARBITRATOR_MODEL,
        max_tokens=1500,
        system=ARBITRATOR_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)


# ── Helpers ────────────────────────────────────────────────────────────────────

def poll_status(path: Path, label: str) -> dict:
    """Block until an agent writes its status file, or timeout."""
    elapsed = 0
    while elapsed < POLL_TIMEOUT:
        if path.exists():
            data = json.loads(path.read_text())
            path.unlink()
            return data
        print(f"  [{label}] waiting... ({elapsed}s)")
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
    return {"status": "failed", "summary": f"timeout after {POLL_TIMEOUT}s"}


def launch(script: str, agent: str, instruction: str, branch: str | None = None):
    """Print the Docker launch line for the human to run in a new terminal."""
    env = f"AGENT={agent} " + (f"BRANCH={branch} " if branch else "")
    print(f"\n{'='*64}")
    print(f"Launch in a new terminal:\n  {env}bash {script}")
    print(f"\nInstruction:\n{instruction}")
    print('='*64 + "\n")


def append_pipeline_log(lines: list[str]):
    """Git-tracked human-readable pipeline log (docs/PIPELINE_LOG.md)."""
    log_file = PROJECT_ROOT / "docs" / "PIPELINE_LOG.md"
    log_file.parent.mkdir(exist_ok=True)
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with log_file.open("a") as f:
        for ln in lines:
            f.write(f"- `{stamp}` {ln}\n")


# ── Spoke: build (flexible mode) ─────────────────────────────────────────────

def run_build(state: DevState) -> dict:
    """Build or fix code. Mode (solo/compete/review) comes from directive."""
    d = state["directive"]
    side = d["side"]                       # "backend" | "frontend"
    mode = d.get("mode", "solo")           # solo | compete | review
    instruction = d.get("instruction", state["task"])

    worker_script = f"docker/run-{side}-worker.sh"
    reviewer_script = f"docker/run-{side}-reviewer.sh"
    status_file = PROJECT_ROOT / ("backend" if side == "backend" else "godot") / ".agent_status.json"
    review_file = PROJECT_ROOT / ".review_output" / f"{side}.json"
    review_file.parent.mkdir(exist_ok=True)

    reports = []

    if mode == "solo":
        launch(worker_script, d["worker_agent"], instruction)
        r = poll_status(status_file, f"{side}-worker")
        reports.append({"side": side, "role": "worker", "agent": d["worker_agent"], **r})

    elif mode == "review":
        launch(worker_script, d["worker_agent"], instruction)
        r = poll_status(status_file, f"{side}-worker")
        reports.append({"side": side, "role": "worker", "agent": d["worker_agent"], **r})

        rev_instr = (
            f"Review the {side} work (READ-ONLY mount). Worker summary: {r.get('summary','')}\n"
            f"Write findings to /work/review_output/{side}.json: "
            f'{{"status":"approved|needs_revision","issues":[...],"summary":"..."}}'
        )
        launch(reviewer_script, d["reviewer_agent"], rev_instr)
        rv = poll_status(review_file, f"{side}-reviewer")
        reports.append({"side": side, "role": "reviewer", "agent": d["reviewer_agent"], **rv})

    elif mode == "compete":
        # Each agent builds on its own branch; arbitrator picks at the hub.
        for ag, br in zip(d["agents"], d["branches"]):
            launch(worker_script, ag, instruction, branch=br)
            r = poll_status(status_file, f"{side}-worker[{br}]")
            reports.append({"side": side, "role": "worker", "agent": ag, "branch": br, **r})

    return {
        "reports": reports,
        f"{side}_status": "built",
        "arbitrator_log": [f"[build:{side}:{mode}] {len(reports)} report(s) collected"],
    }


# ── Spoke: E2E test ───────────────────────────────────────────────────────────

def run_test(state: DevState) -> dict:
    """E2E test engineer writes + runs tests against running services (black-box)."""
    d = state["directive"]
    side = d["side"]                       # "backend" | "frontend"
    instruction = d.get("instruction", "Write and run E2E tests for the new feature.")

    script = f"docker/run-{side}-test.sh"
    result_file = PROJECT_ROOT / ".test_output" / f"{side}.json"
    result_file.parent.mkdir(exist_ok=True)

    launch(script, d["test_agent"], instruction)
    r = poll_status(result_file, f"{side}-test")

    passed = r.get("status") == "pass"
    return {
        f"{side}_status": "test_pass" if passed else "test_fail",
        "test_logs": [{"side": side, "agent": d["test_agent"], **r}],
        "arbitrator_log": [f"[test:{side}] {'PASS' if passed else 'FAIL'}: {r.get('summary','')}"],
    }


# ── Spoke: integration (arbitrator only) ─────────────────────────────────────

def run_integration(state: DevState) -> dict:
    """Arbitrator starts services and runs a smoke check. Final gate before push."""
    print("\n[integration] starting services: docker compose -f docker/docker-compose.dev.yml up -d")
    up = subprocess.run(
        ["docker", "compose", "-f", "docker/docker-compose.dev.yml", "up", "-d", "--build"],
        cwd=PROJECT_ROOT, capture_output=True, text=True,
    )
    # Simple smoke check: backend health endpoint
    time.sleep(8)
    health = subprocess.run(
        ["curl", "-fsS", "http://localhost:8000/api/v1/health"],
        capture_output=True, text=True,
    )
    clean = up.returncode == 0 and health.returncode == 0

    return {
        "test_logs": [{
            "side": "integration", "agent": "arbitrator",
            "status": "pass" if clean else "fail",
            "summary": health.stdout[:200] if clean else (up.stderr or health.stderr)[:200],
        }],
        "arbitrator_log": [f"[integration] {'clean' if clean else 'problems found'}"],
    }


# ── Spoke: push (sole push authority) ────────────────────────────────────────

def run_push(state: DevState) -> dict:
    """ONLY node allowed to push. Commits to a feature branch and pushes."""
    d = state["directive"]
    branch = d.get("branch", f"feature/{int(time.time())}")
    message = d.get("commit_message", f"feat: {state['task']}")

    cmds = [
        ["git", "checkout", "-B", branch],
        ["git", "add", "-A"],
        ["git", "commit", "-m", message],
        ["git", "push", "-u", "origin", branch],
    ]
    outputs = []
    for c in cmds:
        p = subprocess.run(c, cwd=PROJECT_ROOT, capture_output=True, text=True)
        outputs.append(f"{' '.join(c)} → rc={p.returncode}")
        if p.returncode != 0 and c[1] != "commit":  # empty commit is non-fatal
            break

    append_pipeline_log([f"PUSH to {branch}: {message}"] + outputs)
    return {
        "push_done": True,
        "arbitrator_log": [f"[push] branch={branch}"] + outputs,
    }


# ── Hub: analyze + dispatch ───────────────────────────────────────────────────

def analyze_task(state: DevState) -> dict:
    """Arbitrator turns a raw task into the first directive."""
    decision = call_arbitrator(f"""
New task: {state['task']}

Produce the FIRST action. Respond JSON:
{{
  "next_action": "build",            // first step is almost always a build
  "directive": {{
     "side": "backend|frontend",
     "mode": "solo|compete|review",
     "worker_agent": "codex|claude-code",
     "reviewer_agent": "codex|claude-code",   // only if mode=review
     "agents": ["codex","claude-code"],       // only if mode=compete
     "branches": ["agentA","agentB"],         // only if mode=compete
     "instruction": "exact instruction for the agent"
  }},
  "reasoning": "why this side first, why this mode/agent"
}}
""")
    append_pipeline_log([f"TASK: {state['task']}", f"PLAN: {decision['reasoning']}"])
    return {
        "directive": decision["directive"],
        "next_action": decision["next_action"],
        "backend_status": "not_started",
        "frontend_status": "not_started",
        "retry_counts": {},
        "push_done": False,
        "arbitrator_log": [f"[analyze] {decision['reasoning']}"],
    }


def arbitrator_dispatch(state: DevState) -> dict:
    """The HUB. Reads everything, decides the next action + directive."""
    recent_reports = state["reports"][-3:]
    recent_tests = state["test_logs"][-3:]

    decision = call_arbitrator(f"""
Task: {state['task']}
backend_status={state['backend_status']}  frontend_status={state['frontend_status']}
retry_counts={json.dumps(state['retry_counts'])}
push_done={state['push_done']}

Recent build/review reports:
{json.dumps(recent_reports, indent=2, ensure_ascii=False)}

Recent test logs:
{json.dumps(recent_tests, indent=2, ensure_ascii=False)}

Decide the next action. Respond JSON:
{{
  "next_action": "build|test|integrate|push|escalate|done",
  "directive": {{
     // for build:  side, mode, worker_agent, [reviewer_agent | agents+branches], instruction
     // for test:   side, test_agent, instruction
     // for push:   branch, commit_message
     // for integrate/escalate/done: may be empty
  }},
  "reason": "one sentence",
  "escalate_message": "shown to human if next_action=escalate"
}}

Guidance:
- After a build with review: if reviewer found issues and retries remain → next build (fix).
- If a side is built & you want E2E coverage → test that side (mostly frontend playwright).
- If a test failed → build (fix) on that side, passing the failure log in the instruction.
- If both sides are good → integrate.
- If integration was clean → push.
- If integration found problems → test (have the test engineer reproduce/locate the bug).
""")

    action = decision["next_action"]
    updates: dict = {
        "next_action": action,
        "directive": decision.get("directive", {}),
        "arbitrator_log": [f"[dispatch] {action}: {decision.get('reason','')}"],
    }

    # bump retry counter when re-building/re-testing the same side
    if action in ("build", "test"):
        side = decision.get("directive", {}).get("side", "?")
        key = f"{side}_{action}"
        rc = dict(state["retry_counts"])
        rc[key] = rc.get(key, 0) + 1
        updates["retry_counts"] = rc

    if action == "escalate":
        interrupt({"message": decision.get("escalate_message", "Arbitrator needs your decision.")})

    return updates


# ── Routing ────────────────────────────────────────────────────────────────────

def route(state: DevState) -> str:
    return {
        "build": "run_build",
        "test": "run_test",
        "integrate": "run_integration",
        "push": "run_push",
        "escalate": END,    # interrupt already fired inside the hub
        "done": END,
    }.get(state["next_action"], END)


# ── Graph ──────────────────────────────────────────────────────────────────────

def build_graph():
    g = StateGraph(DevState)

    g.add_node("analyze_task", analyze_task)
    g.add_node("arbitrator_dispatch", arbitrator_dispatch)
    g.add_node("run_build", run_build)
    g.add_node("run_test", run_test)
    g.add_node("run_integration", run_integration)
    g.add_node("run_push", run_push)

    g.add_edge(START, "analyze_task")
    g.add_edge("analyze_task", "arbitrator_dispatch")
    g.add_conditional_edges("arbitrator_dispatch", route)

    # every spoke returns to the hub
    g.add_edge("run_build", "arbitrator_dispatch")
    g.add_edge("run_test", "arbitrator_dispatch")
    g.add_edge("run_integration", "arbitrator_dispatch")
    g.add_edge("run_push", "arbitrator_dispatch")

    checkpointer = SqliteSaver.from_conn_string(str(PROJECT_ROOT / ".arbitrator.db"))
    return g.compile(checkpointer=checkpointer)


# ── Entry ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    task = " ".join(sys.argv[1:]) or input("Task: ").strip()
    thread_id = f"task-{int(time.time())}"

    app = build_graph()
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": MAX_TOTAL_STEPS}

    initial = DevState(
        task=task, directive={}, backend_status="not_started", frontend_status="not_started",
        retry_counts={}, next_action="", push_done=False,
        reports=[], test_logs=[], arbitrator_log=[],
    )

    print(f"\nThread: {thread_id}\n")
    for event in app.stream(initial, config=config, stream_mode="values"):
        log = event.get("arbitrator_log", [])
        if log:
            print(f"  {log[-1]}")
