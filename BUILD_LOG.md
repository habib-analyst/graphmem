# GraphMem — Build Log

Built: Sun 2026-10-18 (Graph Hacks, WeMakeDevs × FalkorDB)
Track 02 (Agent Memory and Coordination) + Track 01 double-entry (triage)
Author: Habib Ur Rehman (Pakistan) — github.com/habib-analyst

## Files created

```
graphmem-build/
├── graphmem/
│   ├── __init__.py      # package exports
│   ├── memory.py        # GraphBackend ABC + FalkorDBBackend (real Cypher) + InMemoryBackend (shim)
│   ├── agents.py        # researcher / planner / coder team, recall→act→write-back loop, HANDOFF edges
│   ├── llm.py           # GeminiBackend (GEMINI_API_KEY at runtime, never hardcoded) + MockLLM
│   ├── demo.py          # shared amnesiac-vs-memory comparison logic
│   └── triage.py        # Track 01: decide-and-act triage agent (shortest-path + degree-centrality)
├── tests/
│   ├── test_graphmem.py # 9 tests: CRUD, 2-hop recall, tenant isolation, agent write/read, handoff edge
│   └── test_triage.py   # 4 tests: reasoning path, tenant isolation, BFS, centrality
├── app.py               # FastAPI: POST /chat, GET /memory/graph, GET /demo/compare, POST /triage, web UI
├── demo_compare.py      # scripted demo (doubles as the demo-video script)
├── requirements.txt     # falkordb, fastapi, uvicorn, google-generativeai, pytest, requests
├── docker-compose.yml   # local FalkorDB
├── .env.example         # placeholder-only env template (FALKORDB_URL, GEMINI_API_KEY)
├── .gitignore           # includes .env
├── README.md            # setup + schema + API
└── BUILD_LOG.md         # this file
```

## Test results

`python -m pytest tests/ -q` → **13 passed** (all green, no skips).

| Test | What it checks |
|---|---|
| test_remember_fact_and_recall | semantic fact write + keyword recall |
| test_log_event_and_recall_episodic | episodic event write + recall |
| test_remember_procedure_and_recall | procedural memory write + recall |
| test_two_hop_recall_only_traverses_user_edge | recall follows User→REMEMBERS→Fact, not other users' facts |
| test_tenant_isolation_facts / _events / _graph | cross-tenant data never leaks |
| test_agent_turn_writes_event_and_reads_memory | turn logs event, stores LEARN: fact, injects it into the next prompt |
| test_team_run_creates_handoff_edge | planner→coder HANDOFF edge with summary exists in the graph |
| test_triage_decide_returns_reasoning_path | decide() returns Event→Fact path + decision |
| test_triage_tenant_isolated | triage on another tenant finds nothing |
| test_shortest_path_bfs / test_degree_centrality | graph algorithm helpers |

During the build, two real bugs were caught and fixed by the suite (not hand-waved):
1. `LEARN:` parsing only matched line-starts — real LLM output embeds tags mid-line. Now tags are found anywhere in the reply, and `_clip` strips trailing other-tag segments from captured text.
2. A mis-indented `return reply` stranded inside `_save_procedure` — made `turn()` return None; caught by the handoff test.

## Demo verification

`python demo_compare.py` runs end-to-end offline (MockLLM, in-memory shim).
Web app verified live on uvicorn: `GET /`, `POST /chat`, `GET /memory/graph`,
`GET /demo/compare`, `POST /triage` all return 200 with correct JSON; the SVG
graph visualization and triage panel render in the page.

## Demo transcript (pasted, verbatim)

```
GraphMem demo — graph traversal beats flat vector lookup for agent memory

======================================================================
RUN A — MEMORY OFF (amnesiac agent, fresh graph every time)
======================================================================

--- ticket #1: same report arrives again ---

Agent reply:
  I have no memory of this issue. Starting the investigation from scratch: reproducing the Safari crash, checking auth logs, bisecting the deploy...

--- ticket #2: same report arrives again ---

Agent reply:
  I have no memory of this issue. Starting the investigation from scratch: reproducing the Safari crash, checking auth logs, bisecting the deploy...

======================================================================
RUN B — MEMORY ON (shared FalkorDB graph, planner -> coder team)
======================================================================

--- ticket #1: same report arrives again ---

Researcher:
  Investigated the Safari login crash. Root cause: the auth cookie is missing SameSite=None; Secure, so Safari rejects it and the server throws 500. LEARN: Safari...

Planner:
  I recognize this from our memory graph: Safari login 500 is caused by the auth cookie missing SameSite=None; Secure. No need to re-debug; applying the known fix...

HANDOFF planner -> coder:
  Plan for 'A user reports: the login page crashes on Safari with error 500.': I recognize this from our memory graph: Safari login 500 is caused by the auth cookie missing SameSite=None; Secure. No need to re-debug; applying the known fix and handing off to the coder.

Coder:
  I recognize this from our memory graph: Safari login 500 is caused by the auth cookie missing SameSite=None; Secure. No need to re-debug; applying the known fix...

--- ticket #2: same report arrives again ---

Researcher:
  I recognize this from our memory graph: Safari login 500 is caused by the auth cookie missing SameSite=None; Secure. No need to re-debug; applying the known fix...

Planner:
  I recognize this from our memory graph: Safari login 500 is caused by the auth cookie missing SameSite=None; Secure. No need to re-debug; applying the known fix...

HANDOFF planner -> coder:
  Plan for 'A user reports: the login page crashes on Safari with error 500.': I recognize this from our memory graph: Safari login 500 is caused by the auth cookie missing SameSite=None; Secure. No need to re-debug; applying the known fix and handing off to the coder.

Coder:
  I recognize this from our memory graph: Safari login 500 is caused by the auth cookie missing SameSite=None; Secure. No need to re-debug; applying the known fix...

======================================================================
FINAL MEMORY GRAPH (what the graph learned)
======================================================================
  [Event] [coder] task: Implement this plan (context handed off from planner): I recognize this from our memory graph: S
  [Event] [researcher] task: Research this task: A user reports: the login page crashes on Safari with error 500. -> I r
  [Event] [planner] task: Given this research, make a concrete plan.
Research: Investigated the Safari login crash. Root
  [Fact] Safari login 500 is caused by the auth cookie missing SameSite=None; Secure.
  [Event] [researcher] task: Research this task: A user reports: the login page crashes on Safari with error 500. -> I r
  [Event] [coder] task: Implement this plan (context handed off from planner): I recognize this from our memory graph: S
  [Procedure] fix cookie flags, then verify with a Safari smoke test.
  [Event] [planner] task: Given this research, make a concrete plan.
Research: I recognize this from our memory graph: S
  --HANDOFF--> Plan for 'A user reports: the login page crashes on Safari with error 500.': I recognize this from our memory
  --HANDOFF--> Plan for 'A user reports: the login page crashes on Safari with error 500.': I recognize this from our memory

======================================================================
TAKEAWAY
======================================================================
  Amnesiac agent:   re-debugs the same Safari 500 ticket every time.
  Memory agent:     recalls the cause from the graph, applies the
                    known fix, and hands context to a second agent.
  Track 02: Agent Memory and Coordination — Graph Hacks (WeMakeDevs x FalkorDB)
  Author: Habib Ur Rehman (Pakistan) | github.com/habib-analyst
```

## Honest caveats

1. **Shim vs real FalkorDB:** everything here was verified against `InMemoryBackend`.
   `FalkorDBBackend` (real Cypher, in `graphmem/memory.py`) is written and reviewed
   but was NOT executed — this VM has no Docker and no FalkorDB server. The shim
   mirrors the same semantics (tenant filtering, 2-hop traversal, edge types), so
   the code path transfer is direct, but the Cypher should be smoke-tested once
   against a real server before the demo video.
2. **What needs his FalkorDB Cloud signup:** a real graph to show. Free tier at
   `app.falkordb.cloud/signup`, then set `FALKORDB_URL` and `GRAPHMEM_BACKEND=true`
   in `.env`. Without it the app runs fully on the shim (works, but the pitch
   lands better with real FalkorDB in the video).
3. **Recall matching:** both backends rank by keyword overlap, not embeddings.
   Honest framing for judges: "multi-hop traversal over structured memory" —
   do NOT claim vector/semantic search unless an embedding layer is added later.
4. **MockLLM determinism:** the demo transcript is scripted. With a real
   `GEMINI_API_KEY`, the LEARN:/METHOD: tags in the system prompt steer the
   write-back; a non-cooperative model could skip them (agents still log
   episodic events unconditionally).
5. **Not submitted:** nothing was git-initialized, pushed, or submitted to
   WeMakeDevs — that is the parent's call.

## What was NOT done

- Nothing outstanding on the core: all 7 spec items built and verified.
- Stretch goal (Track 01 triage.py + UI section + 4 tests): DONE — `POST /triage`,
  reasoning path rendered in the UI.
- Open before the deadline: real-FalkorDB smoke test, demo video recording,
  WeMakeDevs submission (parent's call).
