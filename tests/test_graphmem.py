"""GraphMem test suite — runs against InMemoryBackend (no server needed)."""
import sys

sys.path.insert(0, ".")

from graphmem.agents import Agent, Team
from graphmem.llm import MockLLM
from graphmem.memory import InMemoryBackend


def new_backend() -> InMemoryBackend:
    return InMemoryBackend()


# --- memory CRUD -----------------------------------------------------------
def test_remember_fact_and_recall():
    b = new_backend()
    b.remember_fact("t1", "habib", "Safari login 500 is a cookie SameSite issue")
    facts = b.recall_facts("t1", "habib", "Safari login")
    assert len(facts) == 1
    assert "SameSite" in facts[0]["text"]


def test_log_event_and_recall_episodic():
    b = new_backend()
    b.log_event("t1", "s1", "user reported login crash on Safari")
    events = b.recall_episodic("t1", "s1", "Safari crash")
    assert len(events) == 1
    assert events[0]["kind"] == "episodic"


def test_remember_procedure_and_recall():
    b = new_backend()
    b.remember_procedure("t1", "fix cookie flags, then run a Safari smoke test")
    procs = b.recall_procedures("t1", "cookie smoke test")
    assert len(procs) == 1
    assert procs[0]["kind"] == "procedural"


# --- 2-hop recall ----------------------------------------------------------
def test_two_hop_recall_only_traverses_user_edge():
    b = new_backend()
    b.remember_fact("t1", "habib", "habib's fact about safari cookies")
    b.remember_fact("t1", "other", "other person's fact about safari cookies")
    facts = b.recall_facts("t1", "habib", "safari cookies", hops=2)
    assert len(facts) == 1
    assert facts[0]["text"].startswith("habib's fact")


# --- tenant isolation ------------------------------------------------------
def test_tenant_isolation_facts():
    b = new_backend()
    b.remember_fact("tenant-a", "habib", "alpha secret fact")
    b.remember_fact("tenant-b", "habib", "beta secret fact")
    facts = b.recall_facts("tenant-a", "habib", "secret fact")
    assert len(facts) == 1
    assert "alpha" in facts[0]["text"]


def test_tenant_isolation_events():
    b = new_backend()
    b.log_event("tenant-a", "s1", "alpha event")
    b.log_event("tenant-b", "s1", "beta event")
    events = b.recall_episodic("tenant-a", query="event")
    assert len(events) == 1
    assert "alpha" in events[0]["text"]


def test_tenant_isolation_graph():
    b = new_backend()
    b.remember_fact("tenant-a", "habib", "alpha fact")
    b.remember_procedure("tenant-b", "beta procedure")
    g = b.get_graph("tenant-a")
    labels = {n["label"] for n in g["nodes"]}
    assert "Procedure" not in labels
    assert "Fact" in labels


# --- agent turn: writes then reads memory ----------------------------------
def test_agent_turn_writes_event_and_reads_memory():
    b = new_backend()
    llm = MockLLM(script={"research this task": "done. LEARN: sky is blue"},
                  fallback="fallback")
    agent = Agent("researcher", "researcher", b, llm, tenant="t1", user="habib")
    reply = agent.turn("s1", "research this task")
    assert reply == "done. LEARN: sky is blue"

    # episodic event was written
    events = b.recall_episodic("t1", "s1")
    assert any("researcher" in e["text"] for e in events)

    # learned fact was written, and is recalled on the next turn
    facts = b.recall_facts("t1", "habib", "sky")
    assert len(facts) == 1
    assert "sky is blue" in facts[0]["text"]

    # next turn's LLM prompt carries the memory context
    agent.turn("s1", "what color is the sky?")
    last_prompt = llm.calls[-1]["prompt"]
    assert "sky is blue" in last_prompt  # recalled into context


def test_team_run_creates_handoff_edge():
    b = new_backend()
    llm = MockLLM(fallback="ok")
    team = Team(b, llm, tenant="t1")
    out = team.run_task("s1", "build a demo")
    assert out["handoff"]["type"] == "HANDOFF"
    assert "build a demo" in out["handoff"]["props"]["summary"]

    graph = b.get_graph("t1")
    handoffs = [e for e in graph["edges"] if e["type"] == "HANDOFF"]
    assert len(handoffs) == 1
    agents = {n["id"]: n["name"] for n in graph["nodes"] if n["label"] == "Agent"}
    assert agents[handoffs[0]["src"]] == "planner"
    assert agents[handoffs[0]["dst"]] == "coder"
