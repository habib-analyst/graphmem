# GraphMem: a shared memory graph for my agent team

Agents forget. Every session starts from zero, and I end up being the memory of the system. So I built GraphMem: a team of three agents that shares one persistent memory graph in FalkorDB, and recalls context by walking the graph instead of digging through flat embeddings.

That is the 30-second version. Here is the longer one.

## The problem: amnesiac agents

I run a small team of agents: a researcher, a planner, and a coder. They work in sessions, and between sessions they remember nothing. The same bug report lands twice and the whole investigation starts over. I supply the missing context by hand, and that is the most expensive part of the loop.

This is the normal state of agent tooling. Prompts are stateless. Vector stores help with isolated facts, but they flatten everything into points in space. What I actually want when I ask "what did we learn about this bug" is a story: the event, the agent involved, the fact we learned, and the procedure that fixed it. Stories have structure. Embeddings throw the structure away.

## The idea: memory as a graph

So I stopped thinking of memory as a store and started thinking of it as a graph. Three kinds of nodes:

- **Event** (episodic): things that happened. "Session 12: the coder tried approach X on the auth bug. It failed."
- **Fact** (semantic): facts learned. "The auth bug is caused by a stale token cache."
- **Procedure** (procedural): what worked. "Reproducing with the failing test first cut the debugging time."

Users remember facts (`User-[:REMEMBERS]->Fact`), sessions log events (`Session-[:LOGGED]->Event`), and agents hand context to each other as edges (`Agent-[:HANDOFF]->Agent`), so every memory has a who attached to it. Everything is tenant-isolated, so one user's memories never leak into another's.

Recall is then a traversal, not a search. When the coder starts a new session, GraphMem runs a multi-hop Cypher query like this:

```cypher
MATCH (u:User {name:$user, tenant:$tenant})-[:REMEMBERS]->(f:Fact)
WHERE f.tenant = $tenant
RETURN f.text AS text, f.kind AS kind, f.ts AS ts
```

Ranked by keyword overlap with the current task, two hops out from the user. One honest note: this is keyword-overlap traversal over structured memory, not embedding search. I am not claiming vector recall. The graph's advantage is the structure it preserves: what happened, what we learned, what we do next, and which agent was involved, all reachable in one query.

## The build: about 20 hours, one graph

GraphMem is a FastAPI service with a minimal web UI that renders the memory graph live as inline SVG. The FalkorDB layer is written in real Cypher and verified against an in-memory shim with identical semantics (the build machine has no Docker, so the live FalkorDB Cloud free-tier connection is one env var, `FALKORDB_URL`, waiting on my signup). Gemini plugs in behind the three agents via API key; the recorded demo runs on a scripted stand-in so it is reproducible offline.

Each agent writes to the graph as it works. The researcher logs events and facts. The planner writes down what it tried and whether it worked. The coder logs failures so they are never repeated silently. Reads happen at session start, and mid-task, when the planner hands context to the coder as a `HANDOFF` edge instead of re-explaining everything inside a prompt.

Track 02 of Graph Hacks is Agent Memory and Coordination. This is the coordination I actually needed: not agents talking more, but agents sharing a memory they can all walk. As a stretch I also added a Track 01 triage agent that runs multi-hop Cypher (shortest reasoning path from issue to known fix, plus centrality ranking) and shows its path in the UI.

## The demo: amnesiac vs memory

The demo runs the same support ticket twice. A user reports a Safari login crash, error 500. The ticket arrives, gets handled, then the exact same ticket arrives again.

Memory off: the agent says "I have no memory of this issue. Starting the investigation from scratch: reproducing the Safari crash, checking auth logs, bisecting the deploy..." Both times. The full investigation re-runs from zero on the repeat ticket.

Memory on: in the first session the researcher diagnoses the root cause (the auth cookie is missing `SameSite=None; Secure`, so Safari rejects it), and that lands in the graph as a Fact plus a Procedure ("fix cookie flags, then verify with a Safari smoke test"). On the repeat ticket the whole team recalls the cause from the graph immediately. No re-debugging. The planner applies the known fix and hands the context to the coder through a `HANDOFF` edge. The final graph shows the Fact, the Procedure, the session Events, and two HANDOFF edges.

I did not measure wall-clock times, so I will not claim a speedup number. The contrast is behavioral and it is stark: re-investigation versus instant recall with a teammate handoff. A demo video of the full run is linked below.

## What broke, and what is next

The recall is keyword-overlap, not embeddings, which means it misses paraphrases. That is the honest boundary of this build. Second, the live FalkorDB Cloud smoke test is still pending my signup; everything above ran against the shim. Third, I have not measured how recall quality degrades as the graph grows past a few dozen sessions.

Next, I want recall to blend graph traversal with embeddings instead of choosing one, and I want to measure that degradation curve for real. Both are open.

## Links

- Repo: https://github.com/habib-analyst/graphmem (going public before the submission closes)
- Demo video: linked in the repo README
- Built for Graph Hacks (WeMakeDevs x FalkorDB), Track 02: Agent Memory and Coordination, with a Track 01 triage double-entry.

*Habib Ur Rehman, ML/AI engineer.*
