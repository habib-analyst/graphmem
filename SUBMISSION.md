# GraphMem — WeMakeDevs Submission Package

Event: Graph Hacks: Context for AI Agents (WeMakeDevs x FalkorDB)
Submit at: https://www.wemakedevs.org/hackathons/falkordb
Deadline: Sun Oct 18, 2026 ~11:29 PM PKT (11:59 PM IST)
Entrant: Habib Ur Rehman (Pakistan), solo — github.com/habib-analyst

## Tracks
- PRIMARY: Track 02 — Agent Memory and Coordination
- DOUBLE-ENTRY: Track 01 — (decide-and-act triage agent with multi-hop Cypher reasoning paths)

## Paste-ready fields

**Project title:** GraphMem — shared memory graph for agent teams

**Tagline (one line):** Three AI agents sharing one FalkorDB memory graph: episodic, semantic and procedural memory with multi-hop Cypher recall, so the team never debugs the same bug twice.

**Description (paste into the project description box):**
GraphMem gives a team of AI agents (researcher, planner, coder) a shared persistent memory in FalkorDB. Every turn, agents recall relevant memory via multi-hop Cypher traversals and write back what happened: episodic Events, semantic Facts, procedural Procedures, and Agent-to-Agent HANDOFF edges, all tenant-isolated.

The demo runs the same support ticket twice. With memory off, the agent re-runs the full investigation from scratch on the repeat ticket. With memory on, the team recalls the diagnosed root cause from the graph, applies the known fix, and the planner hands context to the coder through a HANDOFF edge. The memory graph renders live in the web UI.

A Track 01 double-entry adds a decide-and-act triage agent: given an issue, it walks the memory graph (shortest reasoning path from issue to known fix, centrality-ranked) and shows its full reasoning path in the UI.

Stack: Python, FalkorDB (primary graph database, central to the product), FastAPI, Gemini API (key via env; scripted stand-in for offline demo), minimal web UI with inline-SVG graph visualization. 13/13 tests green. Built solo during the event window, Oct 15-18.

**Tech stack tags:** Python, FalkorDB, Cypher, FastAPI, Gemini API, multi-agent systems

## Links
- GitHub repo: https://github.com/habib-analyst/graphmem — STATUS: pending creation (parent creates via browser, then approval-card push)
- Demo video: `demo_video.mp4` in the repo — STATUS: in production (worker running)
- Live demo: not deployed (FalkorDB Cloud signup is the entrant's tap; local Docker setup documented in README instead)

## Submission checklist
- [ ] WeMakeDevs account + "Register now" tapped — ENTRANT'S TAP (cannot be done by the agent)
- [ ] GitHub repo created (habib-analyst/graphmem) + code pushed — parent's browser lane
- [ ] Demo video finished and linked — worker in progress
- [ ] Submission panel verified accepting uploads — CAVEAT: panel showed "Loading..." on 2026-10-17 ~12:30 UTC; parent must live-check before submitting
- [ ] BLOG.md published to Dev.to/Hashnode — after repo is public (best-blog side prize)
- [ ] Submit before 11:29 PM PKT Oct 18

## Honest notes for the judges (also in README/BUILD_LOG)
- Recall is keyword-overlap traversal over structured memory, not vector search. No embedding claims.
- Demo runs on a scripted LLM stand-in for reproducibility; Gemini backend is real and key-driven.
- FalkorDB layer is real Cypher, verified against an in-memory shim with identical semantics; Cloud free-tier connection is one env var.
