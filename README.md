# GraphMem

Graph-backed agent memory on **FalkorDB** — Graph Hacks (WeMakeDevs × FalkorDB), **Track 02: Agent Memory and Coordination**.

The pitch: 2–3 agents share one FalkorDB memory graph — episodic nodes (session
events), semantic nodes (facts learned), procedural nodes (what worked). Recall
happens through multi-hop Cypher traversals, not flat vector lookup. Agents
hand off context to each other as graph edges, so coordination is part of the
memory itself.

## Quick start

```bash
pip install --user -r requirements.txt

# Option A: local FalkorDB
docker compose up -d          # see docker-compose.yml (optional)

# Option B: FalkorDB Cloud free tier
# sign up at app.falkordb.cloud/signup and set FALKORDB_URL in your .env

cp .env.example .env          # fill in FALKORDB_URL / GEMINI_API_KEY
uvicorn app:app --port 8000   # web UI at http://localhost:8000
python demo_compare.py        # amnesiac-vs-memory demo script (works offline)
python -m pytest tests/ -q    # test suite (uses the in-memory shim)
```

Without `FALKORDB_URL`/`GRAPHMEM_BACKEND=true` and without `GEMINI_API_KEY`,
everything runs on the in-memory shim + scripted MockLLM — the full demo and
all tests work with zero setup.

## How it works

**Graph schema (tenant-isolated):**

```
(:User {name, tenant}) -[:REMEMBERS]-> (:Fact {text, kind:'semantic', tenant})
(:Session {id, tenant}) -[:LOGGED]-> (:Event {text, kind:'episodic', tenant})
(:Procedure {text, kind:'procedural', tenant})
(:Agent {name}) -[:HANDOFF {summary}]-> (:Agent)
```

**Agent loop (every turn):** recall relevant memory → act via LLM → write back
episodic/semantic/procedural nodes. Handoffs (planner → coder) are recorded as
`HANDOFF` edges with summaries.

**Modules:**

| File | What it does |
|---|---|
| `graphmem/memory.py` | `GraphBackend` ABC + `FalkorDBBackend` (real Cypher) + `InMemoryBackend` (pure-Python shim, identical signatures) |
| `graphmem/agents.py` | researcher / planner / coder sharing one memory; `Team.run_task` does the handoff pipeline |
| `graphmem/llm.py` | `GeminiBackend` (reads `GEMINI_API_KEY` at runtime, never hardcoded) + `MockLLM` (deterministic, for tests/demo) |
| `app.py` | FastAPI: `POST /chat`, `GET /memory/graph`, `GET /` (chat UI + inline SVG graph visualization + triage panel), `GET /demo/compare`, `POST /triage` |
| `demo_compare.py` | Scripted demo: same triage task with memory OFF vs ON — also the demo-video script |
| `graphmem/triage.py` | Track 01 double-entry: decide-and-act triage agent; shortest-path + degree-centrality reasoning over the memory graph, reasoning path shown in UI |

## API

- `POST /chat` `{message, session_id?, agent?}` → agent reply + memory graph
- `GET /memory/graph` → `{nodes, edges}` JSON
- `GET /demo/compare` → amnesiac-vs-memory comparison JSON
- `POST /triage` `{issue}` → `{decision, reasoning_path, candidates, method}` (Track 01)

## Author

Habib Ur Rehman (Pakistan) — github.com/habib-analyst
