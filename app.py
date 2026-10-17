"""GraphMem web app (FastAPI).

- POST /chat            -> one agent turn (memory ON)
- GET  /memory/graph   -> memory graph as JSON for visualization
- GET  /               -> minimal web UI: chat box + SVG memory-graph visualization
- GET  /demo/compare   -> amnesiac-vs-memory comparison as JSON
"""
from __future__ import annotations

import os
import uuid

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from graphmem.agents import Agent, Team
from graphmem.llm import make_llm
from graphmem.memory import make_backend
from graphmem.triage import TriageAgent

app = FastAPI(title="GraphMem", version="0.1.0")

TENANT = os.environ.get("GRAPHMEM_TENANT", "demo")
backend = make_backend()
llm = make_llm()
team = Team(backend, llm, tenant=TENANT)
triage = TriageAgent(backend, llm, tenant=TENANT)


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    agent: str = "planner"  # researcher | planner | coder


@app.post("/chat")
def chat(req: ChatRequest):
    session_id = req.session_id or f"web-{uuid.uuid4().hex[:8]}"
    agent = getattr(team, req.agent, team.planner)
    if not isinstance(agent, Agent):
        agent = team.planner
    reply = agent.turn(session_id, req.message)
    graph = backend.get_graph(TENANT)
    return {
        "agent": agent.name,
        "reply": reply,
        "session_id": session_id,
        "graph": graph,
    }


@app.get("/memory/graph")
def memory_graph():
    return backend.get_graph(TENANT)


@app.get("/demo/compare")
def demo_compare():
    """Same canned task run with memory OFF vs ON, returned as JSON."""
    from graphmem.demo import run_comparison
    return run_comparison()


@app.get("/", response_class=HTMLResponse)
def index():
    return INDEX_HTML


class TriageRequest(BaseModel):
    issue: str


@app.post("/triage")
def triage_issue(req: TriageRequest):
    """Decide-and-act endpoint: shortest-path reasoning over the memory graph."""
    return triage.decide(req.issue)


INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GraphMem — graph memory for agents</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 1100px; margin: 2rem auto; padding: 0 1rem; }
  h1 { margin-bottom: .2rem; } .sub { color: #555; margin-top: 0; }
  #wrap { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }
  #chat { border: 1px solid #ddd; border-radius: 8px; padding: 1rem; }
  #log { height: 300px; overflow-y: auto; border: 1px solid #eee; padding: .5rem; margin-bottom: .5rem; }
  .msg { margin: .4rem 0; } .me { color: #0b5; } .bot { color: #05b; }
  input, select, button { font-size: 1rem; padding: .4rem; }
  #graphBox { border: 1px solid #ddd; border-radius: 8px; padding: 1rem; }
  svg { width: 100%; height: 380px; background: #fafafa; border-radius: 6px; }
  .node { stroke: #333; stroke-width: 1.5px; }
  text { font-size: 11px; pointer-events: none; }
</style>
</head>
<body>
<h1>GraphMem</h1>
<p class="sub">Agent memory on a FalkorDB knowledge graph — recall via multi-hop traversal, not flat lookup.</p>
<div id="wrap">
  <div id="chat">
    <h3>Chat</h3>
    <div id="log"></div>
    <select id="agent"><option>researcher</option><option selected>planner</option><option>coder</option></select>
    <input id="box" size="40" placeholder="Ask the agent...">
    <button onclick="send()">Send</button>
  </div>
  <div id="graphBox">
    <h3>Memory graph</h3>
    <svg id="graph"></svg>
    <button onclick="refresh()">Refresh graph</button>
  </div>
  <div id="triageBox" style="border:1px solid #ddd;border-radius:8px;padding:1rem;margin-top:1.5rem">
    <h3>Triage (Track 01 double-entry): decide-and-act over the graph</h3>
    <input id="issue" size="60" placeholder="Describe an issue, e.g. login page crashes on Safari">
    <button onclick="triage()">Triage</button>
    <div id="triageOut"></div>
  </div>
</div>
<script>
async function triage(){
  const issue=document.getElementById("issue").value; if(!issue) return;
  const r=await fetch("/triage",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({issue})});
  const j=await r.json();
  const out=document.getElementById("triageOut");
  out.innerHTML="<p><b>Decision:</b> "+j.decision+"</p>"
    +"<p><b>Method:</b> "+j.method+"</p>"
    +"<p><b>Reasoning path:</b></p><ol>"
    +j.reasoning_path.map(s=>"<li>["+s.label+"] "+s.text+"</li>").join("")+"</ol>";
  refresh();
}
const colors = {User:"#ffd166", Fact:"#06d6a0", Event:"#118ab2", Session:"#9d4edd",
                Procedure:"#ef476f", Agent:"#f4a261"};
function add(cls, html){ const d=document.createElement("div"); d.className="msg "+cls; d.textContent=html; log.appendChild(d); log.scrollTop=log.scrollHeight; }
async function send(){
  const msg=box.value; if(!msg) return; box.value="";
  add("me","You: "+msg);
  const r=await fetch("/chat",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({message:msg,agent:agent.value,session_id:"web"})});
  const j=await r.json();
  add("bot",j.agent+": "+j.reply);
  draw(j.graph);
}
async function refresh(){
  const r=await fetch("/memory/graph"); draw(await r.json());
}
function draw(g){
  const svg=document.getElementById("graph"); svg.innerHTML="";
  const ns="http://www.w3.org/2000/svg";
  const nodes=g.nodes, n=nodes.length;
  const cx=svg.clientWidth/2||260, cy=190, R=Math.min(cx,cy)-50;
  const pos={};
  nodes.forEach((nd,i)=>{
    const a=2*Math.PI*i/Math.max(n,1);
    pos[nd.id]={x:cx+R*Math.cos(a), y:cy+R*Math.sin(a)};
  });
  g.edges.forEach(e=>{
    if(!pos[e.src]||!pos[e.dst]) return;
    const l=document.createElementNS(ns,"line");
    l.setAttribute("x1",pos[e.src].x); l.setAttribute("y1",pos[e.src].y);
    l.setAttribute("x2",pos[e.dst].x); l.setAttribute("y2",pos[e.dst].y);
    l.setAttribute("stroke","#999"); svg.appendChild(l);
  });
  nodes.forEach(nd=>{
    const c=document.createElementNS(ns,"circle");
    c.setAttribute("cx",pos[nd.id].x); c.setAttribute("cy",pos[nd.id].y);
    c.setAttribute("r",18); c.setAttribute("fill",colors[nd.label]||"#ccc");
    c.setAttribute("class","node"); svg.appendChild(c);
    const t=document.createElementNS(ns,"text");
    t.setAttribute("x",pos[nd.id].x); t.setAttribute("y",pos[nd.id].y+4);
    t.setAttribute("text-anchor","middle"); t.textContent=nd.label; svg.appendChild(t);
  });
}
refresh();
</script>
</body>
</html>
"""
