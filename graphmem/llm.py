"""LLM abstraction. GeminiBackend (real) + MockLLM (scripted, deterministic).

Rules:
- Never hardcode an API key anywhere. GeminiBackend reads GEMINI_API_KEY
  from the environment at runtime only.
- Default to MockLLM when no key is present, so demos and tests work offline.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod


class LLM(ABC):
    @abstractmethod
    def complete(self, prompt: str, agent: str = "agent") -> str:
        """Return a completion for the prompt."""


class MockLLM(LLM):
    """Deterministic scripted responses for tests and offline demos.

    `script` maps a keyword (lowercase substring of the prompt) to a reply.
    The `fallback` is used when nothing matches.
    """

    def __init__(self, script: dict[str, str] | None = None,
                 fallback: str = "I will proceed with the task.") -> None:
        self.script = {k.lower(): v for k, v in (script or {}).items()}
        self.fallback = fallback
        self.calls: list[dict] = []  # record of all prompts, for assertions

    def complete(self, prompt: str, agent: str = "agent") -> str:
        self.calls.append({"agent": agent, "prompt": prompt})
        low = prompt.lower()
        for keyword, reply in self.script.items():
            if keyword in low:
                return reply
        return self.fallback


class GeminiBackend(LLM):
    """Real backend via the google-generativeai package.

    Raises RuntimeError if GEMINI_API_KEY is not set. The package import is
    lazy so the rest of the codebase works without it installed.
    """

    def __init__(self, model: str = "gemini-2.0-flash",
                 api_key: str | None = None) -> None:
        api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Set it in the environment or use MockLLM.")
        try:
            import google.generativeai as genai
        except ImportError as e:
            raise RuntimeError(
                "google-generativeai is not installed. "
                "Run: pip install --user -r requirements.txt") from e
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(model)

    def complete(self, prompt: str, agent: str = "agent") -> str:
        response = self._model.generate_content(prompt)
        return response.text.strip()


def make_llm(script: dict[str, str] | None = None,
             fallback: str = "I will proceed with the task.") -> LLM:
    """Factory: real Gemini when GEMINI_API_KEY is set, else MockLLM."""
    if os.environ.get("GEMINI_API_KEY"):
        try:
            return GeminiBackend()
        except Exception:
            pass
    return MockLLM(script=script, fallback=fallback)
