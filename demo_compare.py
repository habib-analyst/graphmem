#!/usr/bin/env python3
"""GraphMem demo: amnesiac agent vs memory-backed agent on the same task.

This script is the demo-video script. It runs the same support-triage task
twice against a deterministic MockLLM:

  RUN A (memory OFF) — a fresh agent with an empty graph sees the same
      "Safari login 500" ticket twice and starts debugging from scratch both
      times.
  RUN B (memory ON)  — the shared graph records the first session's diagnosis
      and the planner->coder handoff; on the repeat ticket the agent recalls
      the cause and the fix, and hands context to a second agent.

Usage: python demo_compare.py
"""
import sys

sys.path.insert(0, ".")

from graphmem.demo import TASK, run_comparison


def banner(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def show(label: str, text: str) -> None:
    print(f"\n{label}:\n  {text}")


def main() -> None:
    print("\nGraphMem demo — graph traversal beats flat vector lookup for agent memory")
    data = run_comparison()

    banner("RUN A — MEMORY OFF (amnesiac agent, fresh graph every time)")
    for run in data["amnesiac"]:
        print(f"\n--- ticket #{run['run']}: same report arrives again ---")
        show("Agent reply", run["reply"])

    banner("RUN B — MEMORY ON (shared FalkorDB graph, planner -> coder team)")
    for run in data["with_memory"]:
        print(f"\n--- ticket #{run['run']}: same report arrives again ---")
        show("Researcher", run["research"][:160] + ("..." if len(run["research"]) > 160 else ""))
        show("Planner", run["plan"][:160] + ("..." if len(run["plan"]) > 160 else ""))
        show("HANDOFF planner -> coder", run["handoff_summary"])
        show("Coder", run["implementation"][:160] + ("..." if len(run["implementation"]) > 160 else ""))

    banner("FINAL MEMORY GRAPH (what the graph learned)")
    graph = data["graph"]
    for n in graph["nodes"]:
        if n.get("label") in ("Fact", "Event", "Procedure"):
            print(f"  [{n['label']}] {n.get('text', '')[:110]}")
    for e in graph["edges"]:
        if e["type"] == "HANDOFF":
            print(f"  --{e['type']}--> {e['props'].get('summary', '')[:110]}")

    banner("TAKEAWAY")
    print("  Amnesiac agent:   re-debugs the same Safari 500 ticket every time.")
    print("  Memory agent:     recalls the cause from the graph, applies the")
    print("                    known fix, and hands context to a second agent.")
    print("  Track 02: Agent Memory and Coordination — Graph Hacks (WeMakeDevs x FalkorDB)")
    print("  Author: Habib Ur Rehman (Pakistan) | github.com/habib-analyst")


if __name__ == "__main__":
    main()
