"""GraphMem agents: researcher, planner, coder sharing one memory graph.

Every agent turn follows the same loop:
  1. RECALL: pull semantic facts, episodic events, and procedures from memory.
  2. ACT: call the LLM with memory injected as context.
  3. WRITE BACK: log the turn as an episodic event, save learned facts/procedures.

Handoffs: planner -> coder is recorded as a HANDOFF edge with a summary, so
context transfers inside the graph rather than disappearing between agents.
"""
from __future__ import annotations

from .llm import LLM
from .memory import GraphBackend


class Agent:
    def __init__(self, name: str, role: str, backend: GraphBackend, llm: LLM,
                 tenant: str = "demo", user: str = "habib") -> None:
        self.name = name
        self.role = role
        self.backend = backend
        self.llm = llm
        self.tenant = tenant
        self.user = user

    def turn(self, session_id: str, message: str) -> str:
        """One agent turn: recall -> act -> write back."""
        facts = self.backend.recall_facts(self.tenant, self.user, message, hops=2)
        events = self.backend.recall_episodic(self.tenant, session_id, message)
        procedures = self.backend.recall_procedures(self.tenant, message)

        context = self._build_context(facts, events, procedures)
        prompt = (f"You are {self.name}, a {self.role} in a multi-agent team.\n"
                  f"{context}\nUser task: {message}\n"
                  f"Respond concisely. If you learn a durable fact, prefix it with "
                  f"LEARN: and the fact. If you discover a method that worked, "
                  f"prefix it with METHOD: and the method.")
        reply = self.llm.complete(prompt, agent=self.name)

        # Write back: episodic event always; facts/procedures from tagged lines.
        self.backend.log_event(self.tenant, session_id,
                               f"[{self.name}] task: {message} -> {reply[:200]}")
        for line in reply.splitlines():
            upper = line.upper()
            for tag, writer in (("LEARN:", self._save_fact),
                                ("METHOD:", self._save_procedure)):
                if tag in upper:
                    writer(self._clip(line[upper.index(tag) + len(tag):].strip()))
        return reply

    @staticmethod
    def _clip(text: str) -> str:
        """Cut trailing other-tag segments out of a captured memory."""
        for other in ("LEARN:", "METHOD:"):
            idx = text.upper().find(other)
            if idx >= 0:
                text = text[:idx].strip()
        return text

    def _save_fact(self, text: str) -> None:
        if text:
            self.backend.remember_fact(self.tenant, self.user, text)

    def _save_procedure(self, text: str) -> None:
        if text:
            self.backend.remember_procedure(self.tenant, text)

    def _build_context(self, facts: list, events: list, procedures: list) -> str:
        parts = []
        if facts:
            parts.append("Relevant facts from memory:\n" +
                         "\n".join(f"- {f['text']}" for f in facts[:5]))
        if events:
            parts.append("Earlier in this session:\n" +
                         "\n".join(f"- {e['text']}" for e in events[:5]))
        if procedures:
            parts.append("Methods that worked before:\n" +
                         "\n".join(f"- {p['text']}" for p in procedures[:3]))
        if not parts:
            return "Memory is empty. Work from first principles."
        return "\n\n".join(parts)


class Team:
    """The three-agent team sharing one memory backend."""

    def __init__(self, backend: GraphBackend, llm: LLM,
                 tenant: str = "demo", user: str = "habib") -> None:
        self.backend = backend
        self.llm = llm
        self.researcher = Agent("researcher", "research agent that investigates and gathers evidence",
                               backend, llm, tenant, user)
        self.planner = Agent("planner", "planning agent that turns research into an action plan",
                             backend, llm, tenant, user)
        self.coder = Agent("coder", "coding agent that implements the plan", backend, llm,
                           tenant, user)

    def run_task(self, session_id: str, task: str) -> dict:
        """Run the full pipeline: researcher -> planner -> HANDOFF -> coder."""
        research = self.researcher.turn(session_id, f"Research this task: {task}")
        plan = self.planner.turn(session_id,
                                 f"Given this research, make a concrete plan.\nResearch: {research}")
        handoff = self.backend.handoff("planner", "coder",
                                       f"Plan for '{task}': {plan[:200]}")
        code = self.coder.turn(session_id,
                               f"Implement this plan (context handed off from planner): {plan}")
        return {
            "research": research,
            "plan": plan,
            "handoff": handoff,
            "implementation": code,
            "handoff_summary": handoff["props"]["summary"],
        }
