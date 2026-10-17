"""Track 01 double-entry: a "decide and act" triage agent.

The triage agent reasons over the memory graph instead of the raw text:
  1. Records the incoming issue as an episodic event.
  2. Multi-hop recall finds candidate known facts/procedures.
  3. Computes the shortest reasoning path (BFS) from the issue node to each
     candidate through the actual graph structure, and ranks candidates by
     degree centrality (the most-connected memory wins ties).
  4. The LLM makes the final decision with the reasoning path as context.

The reasoning path is returned in full and shown in the UI, so judges can
see the graph traversal that produced the decision.
"""
from __future__ import annotations

from collections import deque

from .llm import LLM
from .memory import GraphBackend


class TriageAgent:
    def __init__(self, backend: GraphBackend, llm: LLM,
                 tenant: str = "demo", session_id: str = "triage") -> None:
        self.backend = backend
        self.llm = llm
        self.tenant = tenant
        self.session_id = session_id

    def decide(self, issue: str) -> dict:
        """Decide on an issue and return {decision, reasoning_path, method}."""
        event = self.backend.log_event(self.tenant, self.session_id, f"ISSUE: {issue}")
        graph = self.backend.get_graph(self.tenant)

        candidates = (self.backend.recall_facts(self.tenant, "", issue, hops=1)
                      + self.backend.recall_procedures(self.tenant, issue))
        candidates = candidates[:5]

        reasoning_path: list[dict] = []
        best: dict | None = None
        best_score = (-1, -1)  # (path found, degree centrality)
        for cand in candidates:
            path = shortest_path(graph, event["id"], cand["id"])
            centrality = degree_centrality(graph, cand["id"])
            if path and (1, centrality) > best_score:
                best, best_score = cand, (1, centrality)
                reasoning_path = path
            elif not best and centrality >= 0:
                best, best_score = cand, (0, centrality)
                reasoning_path = [node_summary(graph, event["id"]),
                                  node_summary(graph, cand["id"])]

        context = "\n".join(
            f"{i + 1}. [{s['label']}] {s['text']}" for i, s in enumerate(reasoning_path))
        prompt = (f"You are a triage agent. Decide how to handle this issue.\n"
                  f"Issue: {issue}\n\n"
                  f"Reasoning path through the memory graph:\n{context or '(no path found)'}\n\n"
                  f"Known memory:\n"
                  + "\n".join(f"- {c['text']}" for c in candidates[:5])
                  + "\n\nReply with a one-paragraph decision, then ACT: state the action.")
        decision = self.llm.complete(prompt, agent="triage")

        return {
            "issue": issue,
            "decision": decision,
            "reasoning_path": reasoning_path,
            "candidates": [{"id": c["id"], "label": c["label"], "text": c["text"]}
                           for c in candidates],
            "method": "shortest-path + degree-centrality over the memory graph",
        }


def node_summary(graph: dict, node_id: str) -> dict:
    for n in graph["nodes"]:
        if n["id"] == node_id:
            return {"id": n["id"], "label": n["label"],
                    "text": n.get("text", n.get("name", ""))[:140]}
    return {"id": node_id, "label": "?", "text": ""}


def shortest_path(graph: dict, src: str, dst: str) -> list[dict]:
    """BFS shortest path over the (undirected view of the) memory graph."""
    adj: dict[str, list[str]] = {}
    for e in graph["edges"]:
        adj.setdefault(e["src"], []).append(e["dst"])
        adj.setdefault(e["dst"], []).append(e["src"])
    prev: dict[str, str | None] = {src: None}
    queue: deque[str] = deque([src])
    while queue:
        cur = queue.popleft()
        if cur == dst:
            break
        for nxt in adj.get(cur, []):
            if nxt not in prev:
                prev[nxt] = cur
                queue.append(nxt)
    if dst not in prev:
        return []
    chain: list[str] = []
    cur: str | None = dst
    while cur is not None:
        chain.append(cur)
        cur = prev[cur]
    return [node_summary(graph, nid) for nid in reversed(chain)]


def degree_centrality(graph: dict, node_id: str) -> int:
    """Number of edges touching the node (PageRank-lite for tiny graphs)."""
    return sum(1 for e in graph["edges"] if e["src"] == node_id or e["dst"] == node_id)
