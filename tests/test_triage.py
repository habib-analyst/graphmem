"""Track 01 triage tests."""
import sys

sys.path.insert(0, ".")

from graphmem.llm import MockLLM
from graphmem.memory import InMemoryBackend
from graphmem.triage import TriageAgent, degree_centrality, shortest_path


def seed(b: InMemoryBackend) -> None:
    b.remember_fact("t1", "habib", "Safari login 500 is caused by a cookie SameSite issue")
    b.remember_procedure("t1", "fix cookie flags, then run a Safari smoke test")
    b.remember_fact("t1", "habib", "unrelated fact about databases")


def test_triage_decide_returns_reasoning_path():
    b = InMemoryBackend()
    seed(b)
    llm = MockLLM(fallback="Decision: apply the known cookie fix. ACT: patch cookie flags.")
    agent = TriageAgent(b, llm, tenant="t1")
    out = agent.decide("login page crashes on Safari with error 500")
    assert "cookie" in out["decision"].lower()
    assert len(out["reasoning_path"]) >= 2
    labels = [s["label"] for s in out["reasoning_path"]]
    assert labels[0] == "Event"          # the issue node
    assert labels[-1] in ("Fact", "Procedure")  # the known fix
    assert out["method"].startswith("shortest-path")


def test_triage_tenant_isolated():
    b = InMemoryBackend()
    seed(b)
    llm = MockLLM(fallback="Decision: investigate fresh.")
    agent = TriageAgent(b, llm, tenant="other")
    out = agent.decide("login page crashes on Safari")
    assert out["candidates"] == []
    assert out["reasoning_path"] == []


def test_shortest_path_bfs():
    graph = {"nodes": [{"id": "a", "label": "Event"},
                       {"id": "b", "label": "Session"},
                       {"id": "c", "label": "Fact"}],
             "edges": [{"src": "a", "dst": "b", "type": "LOGGED", "props": {}},
                       {"src": "b", "dst": "c", "type": "LOGGED", "props": {}}]}
    path = shortest_path(graph, "a", "c")
    assert [s["id"] for s in path] == ["a", "b", "c"]
    assert shortest_path(graph, "a", "zzz") == []


def test_degree_centrality():
    graph = {"nodes": [{"id": "a", "label": "Event"}, {"id": "b", "label": "Fact"}],
             "edges": [{"src": "a", "dst": "b", "type": "X", "props": {}},
                       {"src": "a", "dst": "b", "type": "Y", "props": {}}]}
    assert degree_centrality(graph, "a") == 2
    assert degree_centrality(graph, "b") == 2
    assert degree_centrality(graph, "nope") == 0
