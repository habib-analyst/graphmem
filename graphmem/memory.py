"""GraphMem memory layer: a graph-backed memory for AI agents.

Two backends share one interface:
- FalkorDBBackend: talks to a real FalkorDB server (needs FALKORDB_URL or localhost:6379).
- InMemoryBackend: pure-Python shim with identical method signatures for tests/offline work.

Schema (tenant-isolated, tenant lives on nodes and every query filters by it):
  (:User {name, tenant})-[:REMEMBERS]->(:Fact {text, kind:'semantic', tenant, ts})
  (:Session {id, tenant})-[:LOGGED]->(:Event {text, kind:'episodic', tenant, ts})
  (:Procedure {text, kind:'procedural', tenant, ts})
  (:Agent {name})-[:HANDOFF {summary, ts}]->(:Agent)
"""
from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod


def _now() -> float:
    return time.time()


class GraphBackend(ABC):
    """Backend contract. Every write carries a tenant; every read filters by it."""

    @abstractmethod
    def remember_fact(self, tenant: str, user: str, text: str, kind: str = "semantic") -> dict:
        """Store a semantic fact under tenant/user."""

    @abstractmethod
    def log_event(self, tenant: str, session_id: str, text: str) -> dict:
        """Store an episodic event under tenant/session."""

    @abstractmethod
    def remember_procedure(self, tenant: str, text: str) -> dict:
        """Store a procedural memory ("what worked") under tenant."""

    @abstractmethod
    def recall_facts(self, tenant: str, user: str, query: str, hops: int = 2) -> list:
        """Multi-hop semantic recall: facts connected to the query (or user)."""

    @abstractmethod
    def recall_episodic(self, tenant: str, session_id: str | None = None,
                        query: str | None = None) -> list:
        """Recall episodic events, optionally filtered by session/query."""

    @abstractmethod
    def recall_procedures(self, tenant: str, query: str | None = None) -> list:
        """Recall procedural memories, optionally filtered by query."""

    @abstractmethod
    def handoff(self, from_agent: str, to_agent: str, summary: str) -> dict:
        """Record an agent->agent handoff edge with a summary."""

    @abstractmethod
    def get_graph(self, tenant: str) -> dict:
        """Full memory graph for a tenant as JSON (nodes + edges) for visualization."""


# ----------------------------------------------------------------------------
# In-memory shim: identical signatures, no server required.
# ----------------------------------------------------------------------------
class InMemoryBackend(GraphBackend):
    """Pure-Python property-graph shim.

    Keeps the same Cypher-style semantics (2-hop recall, tenant filtering)
    so everything testable here transfers to FalkorDB.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, dict] = {}   # node_id -> node
        self._edges: list[dict] = []        # {src, dst, type, props}
        self._counter = 0

    # -- internal ---------------------------------------------------------
    def _add_node(self, label: str, props: dict) -> dict:
        self._counter += 1
        node = {"id": f"n{self._counter}", "label": label, **props}
        self._nodes[node["id"]] = node
        return node

    def _add_edge(self, src: str, dst: str, rel_type: str, props: dict | None = None) -> dict:
        edge = {"src": src, "dst": dst, "type": rel_type, "props": props or {}}
        self._edges.append(edge)
        return edge

    def _match(self, query: str, nodes: list[dict]) -> list[dict]:
        """Token-overlap match (stand-in for full-text / vector search)."""
        if not query:
            return nodes
        q = set(query.lower().split())
        scored = []
        for n in nodes:
            text = str(n.get("text", n.get("name", ""))).lower()
            hits = len(q & set(text.split()))
            if hits:
                scored.append((hits, n))
        scored.sort(key=lambda x: -x[0])
        return [n for _, n in scored]

    # -- writes -----------------------------------------------------------
    def remember_fact(self, tenant: str, user: str, text: str, kind: str = "semantic") -> dict:
        user_node = self._ensure_user(user, tenant)
        fact = self._add_node("Fact", {"text": text, "kind": kind, "tenant": tenant, "ts": _now()})
        self._add_edge(user_node["id"], fact["id"], "REMEMBERS")
        return fact

    def log_event(self, tenant: str, session_id: str, text: str) -> dict:
        session_node = self._ensure_session(session_id, tenant)
        event = self._add_node("Event", {"text": text, "kind": "episodic",
                                        "tenant": tenant, "ts": _now()})
        self._add_edge(session_node["id"], event["id"], "LOGGED")
        return event

    def remember_procedure(self, tenant: str, text: str) -> dict:
        proc = self._add_node("Procedure", {"text": text, "kind": "procedural",
                                           "tenant": tenant, "ts": _now()})
        return proc

    def handoff(self, from_agent: str, to_agent: str, summary: str) -> dict:
        a = self._ensure_agent(from_agent)
        b = self._ensure_agent(to_agent)
        return self._add_edge(a["id"], b["id"], "HANDOFF", {"summary": summary, "ts": _now()})

    # -- reads ------------------------------------------------------------
    def recall_facts(self, tenant: str, user: str, query: str, hops: int = 2) -> list:
        """2-hop recall: User -[:REMEMBERS]-> Fact, matched against the query.

        Mimics: MATCH (u:User {name, tenant})-[:REMEMBERS]->(f:Fact)
                WHERE f.tenant = tenant AND f.text CONTAINS query-tokens RETURN f
        """
        facts = [n for n in self._nodes.values()
                 if n["label"] == "Fact" and n.get("tenant") == tenant]
        if hops >= 2 and user:
            user_ids = {n["id"] for n in self._nodes.values()
                        if n["label"] == "User" and n.get("name") == user
                        and n.get("tenant") == tenant}
            rem = {(e["src"], e["dst"]) for e in self._edges if e["type"] == "REMEMBERS"}
            facts = [f for f in facts if any((uid, f["id"]) in rem for uid in user_ids)]
        return self._match(query, facts)

    def recall_episodic(self, tenant: str, session_id: str | None = None,
                        query: str | None = None) -> list:
        events = [n for n in self._nodes.values()
                  if n["label"] == "Event" and n.get("tenant") == tenant]
        if session_id:
            sess_ids = {n["id"] for n in self._nodes.values()
                        if n["label"] == "Session" and n.get("id") == session_id
                        and n.get("tenant") == tenant}
            logged = {(e["src"], e["dst"]) for e in self._edges if e["type"] == "LOGGED"}
            events = [e for e in events if any((sid, e["id"]) in logged for sid in sess_ids)]
        events.sort(key=lambda n: n.get("ts", 0), reverse=True)
        return self._match(query, events)

    def recall_procedures(self, tenant: str, query: str | None = None) -> list:
        procs = [n for n in self._nodes.values()
                 if n["label"] == "Procedure" and n.get("tenant") == tenant]
        procs.sort(key=lambda n: n.get("ts", 0), reverse=True)
        return self._match(query, procs)

    def get_graph(self, tenant: str) -> dict:
        ids = {nid for nid, n in self._nodes.items() if n.get("tenant") == tenant}
        # Agents are tenantless by design (a shared workforce); include connected ones.
        agent_ids = {nid for nid, n in self._nodes.items() if n["label"] == "Agent"}
        edges = [e for e in self._edges
                 if e["src"] in ids or e["src"] in agent_ids]
        nodes = [self._nodes[nid] for nid in ids | {e["src"] for e in edges} | {e["dst"] for e in edges}]
        return {"nodes": nodes, "edges": edges}

    # -- helpers ----------------------------------------------------------
    def _ensure_user(self, name: str, tenant: str) -> dict:
        for n in self._nodes.values():
            if n["label"] == "User" and n.get("name") == name and n.get("tenant") == tenant:
                return n
        return self._add_node("User", {"name": name, "tenant": tenant, "ts": _now()})

    def _ensure_session(self, session_id: str, tenant: str) -> dict:
        for n in self._nodes.values():
            if n["label"] == "Session" and n.get("id") == session_id \
                    and n.get("tenant") == tenant:
                return n
        return self._add_node("Session", {"id": session_id, "tenant": tenant, "ts": _now()})

    def _ensure_agent(self, name: str) -> dict:
        for n in self._nodes.values():
            if n["label"] == "Agent" and n.get("name") == name:
                return n
        return self._add_node("Agent", {"name": name, "ts": _now()})


# ----------------------------------------------------------------------------
# FalkorDB backend: real Cypher against a FalkorDB server.
# ----------------------------------------------------------------------------
class FalkorDBBackend(GraphBackend):
    """Real backend. Needs `pip install falkordb` and a reachable server.

    FALKORDB_URL examples:
      redis://localhost:6379
      redis://:password@host:6379
      redis+ssl://user:pass@host:port
    """

    GRAPH = "graphmem"

    def __init__(self, url: str | None = None, graph: str | None = None) -> None:
        from falkordb import FalkorDB  # lazy import: not needed for shim/tests
        url = url or os.environ.get("FALKORDB_URL", "redis://localhost:6379")
        self._client = FalkorDB.from_url(url)
        self._g = self._client.select_graph(graph or self.GRAPH)

    # -- writes -----------------------------------------------------------
    def remember_fact(self, tenant: str, user: str, text: str, kind: str = "semantic") -> dict:
        q = """
        MERGE (u:User {name:$user, tenant:$tenant})
        CREATE (f:Fact {text:$text, kind:$kind, tenant:$tenant, ts:timestamp()})
        CREATE (u)-[:REMEMBERS]->(f) RETURN f
        """
        return self._row(q, {"user": user, "tenant": tenant, "text": text, "kind": kind})

    def log_event(self, tenant: str, session_id: str, text: str) -> dict:
        q = """
        MERGE (s:Session {id:$sid, tenant:$tenant})
        CREATE (e:Event {text:$text, kind:'episodic', tenant:$tenant, ts:timestamp()})
        CREATE (s)-[:LOGGED]->(e) RETURN e
        """
        return self._row(q, {"sid": session_id, "tenant": tenant, "text": text})

    def remember_procedure(self, tenant: str, text: str) -> dict:
        q = """
        CREATE (p:Procedure {text:$text, kind:'procedural', tenant:$tenant, ts:timestamp()})
        RETURN p
        """
        return self._row(q, {"text": text, "tenant": tenant})

    def handoff(self, from_agent: str, to_agent: str, summary: str) -> dict:
        q = """
        MERGE (a:Agent {name:$from}) MERGE (b:Agent {name:$to})
        CREATE (a)-[h:HANDOFF {summary:$summary, ts:timestamp()}]->(b)
        RETURN a.name AS src, b.name AS dst, h.summary AS summary
        """
        return self._row(q, {"from": from_agent, "to": to_agent, "summary": summary})

    # -- reads ------------------------------------------------------------
    def recall_facts(self, tenant: str, user: str, query: str, hops: int = 2) -> list:
        # 2-hop: User -[:REMEMBERS]-> Fact, ranked by keyword overlap with query.
        q = """
        MATCH (u:User {name:$user, tenant:$tenant})-[:REMEMBERS]->(f:Fact)
        WHERE f.tenant = $tenant RETURN f.text AS text, f.kind AS kind, f.ts AS ts
        """
        rows = self._rows(q, {"user": user, "tenant": tenant})
        return self._rank(rows, query)

    def recall_episodic(self, tenant: str, session_id: str | None = None,
                        query: str | None = None) -> list:
        if session_id:
            q = """
            MATCH (s:Session {id:$sid, tenant:$tenant})-[:LOGGED]->(e:Event)
            WHERE e.tenant = $tenant RETURN e.text AS text, e.ts AS ts ORDER BY e.ts DESC
            """
            rows = self._rows(q, {"sid": session_id, "tenant": tenant})
        else:
            q = """
            MATCH (e:Event) WHERE e.tenant = $tenant
            RETURN e.text AS text, e.ts AS ts ORDER BY e.ts DESC
            """
            rows = self._rows(q, {"tenant": tenant})
        return self._rank(rows, query or "")

    def recall_procedures(self, tenant: str, query: str | None = None) -> list:
        q = """
        MATCH (p:Procedure) WHERE p.tenant = $tenant
        RETURN p.text AS text, p.ts AS ts ORDER BY p.ts DESC
        """
        rows = self._rows(q, {"tenant": tenant})
        return self._rank(rows, query or "")

    def get_graph(self, tenant: str) -> dict:
        q = """
        MATCH (n) WHERE n.tenant = $tenant OR n:Agent
        OPTIONAL MATCH (n)-[r]->(m)
        RETURN n, r, m
        """
        nodes: dict[int, dict] = {}
        edges: list[dict] = []
        result = self._g.query(q, {"tenant": tenant})
        for row in result.result_set:
            n, r, m = row
            if n is not None:
                nodes[n.id] = {"id": n.id, "label": next(iter(n.labels or ["Node"])),
                               **n.properties}
            if r is not None and m is not None:
                nodes[m.id] = {"id": m.id, "label": next(iter(m.labels or ["Node"])),
                               **m.properties}
                edges.append({"src": r.src_node, "dst": r.dest_node,
                              "type": r.relation_type, "props": r.properties})
        return {"nodes": list(nodes.values()), "edges": edges}

    # -- helpers ----------------------------------------------------------
    def _row(self, q: str, params: dict) -> dict:
        return self._g.query(q, params).result_set[0]

    def _rows(self, q: str, params: dict) -> list:
        return [dict(zip(self._g.query(q, params).header, r))
                for r in self._g.query(q, params).result_set]

    @staticmethod
    def _rank(rows: list[dict], query: str) -> list[dict]:
        if not query:
            return rows
        q = set(query.lower().split())
        scored = sorted(
            (len(q & set(str(r.get("text", "")).lower().split())), i, r)
            for i, r in enumerate(rows))
        return [r for s, _, r in sorted(scored, reverse=True) if s > 0 or not query]


def make_backend(kind: str | None = None) -> GraphBackend:
    """Factory: 'falkor' -> FalkorDBBackend, anything else -> InMemoryBackend.

    Use FALKORDB_USE=true to try the real server; falls back to the shim if the
    connection fails, so the app always boots.
    """
    kind = kind or os.environ.get("GRAPHMEM_BACKEND", "")
    if kind.lower() in ("falkor", "falkordb", "true", "1"):
        try:
            return FalkorDBBackend()
        except Exception:
            pass
    return InMemoryBackend()
