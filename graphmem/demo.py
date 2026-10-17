"""Shared amnesiac-vs-memory comparison logic (used by demo_compare.py and app.py)."""
from __future__ import annotations

from .agents import Agent, Team
from .llm import MockLLM
from .memory import InMemoryBackend

TASK = "A user reports: the login page crashes on Safari with error 500."

AMNESIAC_FALLBACK = (
    "I have no memory of this issue. Starting the investigation from scratch: "
    "reproducing the Safari crash, checking auth logs, bisecting the deploy...")

INVESTIGATE_REPLY = (
    "Investigated the Safari login crash. Root cause: the auth cookie is "
    "missing SameSite=None; Secure, so Safari rejects it and the server "
    "throws 500. LEARN: Safari login 500 is caused by the auth cookie "
    "missing SameSite=None; Secure. "
    "METHOD: fix cookie flags, then verify with a Safari smoke test.")

RECALL_REPLY = (
    "I recognize this from our memory graph: Safari login 500 is caused by "
    "the auth cookie missing SameSite=None; Secure. No need to re-debug; "
    "applying the known fix and handing off to the coder.")


def run_comparison() -> dict:
    """Run the same triage task with memory OFF vs ON. Returns structured data."""
    amnesiac: list[dict] = []
    for i in (1, 2):
        llm = MockLLM(script={}, fallback=AMNESIAC_FALLBACK)
        agent = Agent("planner", "support agent", InMemoryBackend(), llm, tenant="a")
        amnesiac.append({"run": i, "reply": agent.turn("session-x", TASK)})

    backend = InMemoryBackend()
    llm = MockLLM(script={
        "safari login 500 is caused": RECALL_REPLY,
        "research this task": INVESTIGATE_REPLY,
    }, fallback=RECALL_REPLY)
    team = Team(backend, llm, tenant="demo")
    with_memory: list[dict] = []
    for i in (1, 2):
        out = team.run_task("session-x", TASK)
        with_memory.append({"run": i, **out})

    return {
        "task": TASK,
        "amnesiac": amnesiac,
        "with_memory": with_memory,
        "graph": backend.get_graph("demo"),
    }
