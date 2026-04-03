"""
CrewAI tracing wrapper for AMO.

CrewAI does not use LangChain callbacks, so we wrap Crew.kickoff() directly.
One span is emitted per kickoff() call. Per-task spans are phase 2.

Usage::

    from crewai import Crew, Agent, Task
    from amo.wrappers import AmoCrewWrapper

    crew = Crew(agents=[...], tasks=[...])
    traced = AmoCrewWrapper(crew)

    result = traced.kickoff()
    result = traced.kickoff(inputs={"topic": "AI"})
    result = await traced.kickoff_async()
"""

from __future__ import annotations

import time
from typing import Any

from ..emitter import get_emitter
from ..models import ErrorDetail, TraceEvent


class AmoCrewWrapper:
    """
    Wraps a CrewAI Crew instance and emits an AMO trace event for each kickoff.

    Token usage is read from crew.usage_metrics after execution where available.
    """

    def __init__(self, crew: Any, agent_name: str | None = None) -> None:
        """
        Args:
            crew: A crewai.Crew instance.
            agent_name: Label for this crew in AMO. Defaults to the name of the
                        first agent, or 'crew' if not determinable.
        """
        self._crew = crew
        self._agent_name = agent_name or _infer_agent_name(crew)

    def kickoff(self, inputs: dict[str, Any] | None = None) -> Any:
        """Traced synchronous crew kickoff."""
        start = time.perf_counter()
        event = TraceEvent(
            framework="crewai",
            agent_name=self._agent_name,
            action="kickoff",
        )
        exc_captured: BaseException | None = None
        try:
            result = self._crew.kickoff(inputs=inputs) if inputs else self._crew.kickoff()
            return result
        except BaseException as exc:
            exc_captured = exc
            raise
        finally:
            self._emit(event, start, exc_captured)

    async def kickoff_async(self, inputs: dict[str, Any] | None = None) -> Any:
        """Traced asynchronous crew kickoff."""
        start = time.perf_counter()
        event = TraceEvent(
            framework="crewai",
            agent_name=self._agent_name,
            action="kickoff_async",
        )
        exc_captured: BaseException | None = None
        try:
            if inputs:
                result = await self._crew.kickoff_async(inputs=inputs)
            else:
                result = await self._crew.kickoff_async()
            return result
        except BaseException as exc:
            exc_captured = exc
            raise
        finally:
            self._emit(event, start, exc_captured)

    def _emit(
        self,
        event: TraceEvent,
        start: float,
        exc: BaseException | None,
    ) -> None:
        duration_ms = int((time.perf_counter() - start) * 1000)
        usage = _extract_usage(self._crew)

        updates: dict[str, Any] = {
            "duration_ms": duration_ms,
            **usage,
        }
        if exc is not None:
            updates["status"] = "error"
            updates["error"] = ErrorDetail(
                error_type=type(exc).__name__,
                message=str(exc),
            )
        else:
            updates["status"] = "success"

        final = event.model_copy(update=updates)
        try:
            get_emitter().emit(final)
        except Exception:
            pass

    def __getattr__(self, name: str) -> Any:
        """Proxy all other crew attributes/methods transparently."""
        return getattr(self._crew, name)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _infer_agent_name(crew: Any) -> str:
    try:
        agents = crew.agents
        if agents:
            first = agents[0]
            return getattr(first, "role", None) or getattr(first, "name", None) or "crew"
    except Exception:
        pass
    return "crew"


def _extract_usage(crew: Any) -> dict[str, Any]:
    """
    Read token usage from crew.usage_metrics if available.
    CrewAI populates this after kickoff() completes.
    """
    try:
        metrics = getattr(crew, "usage_metrics", None)
        if metrics is None:
            return {}
        # UsageMetrics has total_tokens, prompt_tokens, completion_tokens
        return {
            "input_tokens": int(getattr(metrics, "prompt_tokens", 0) or 0),
            "output_tokens": int(getattr(metrics, "completion_tokens", 0) or 0),
        }
    except Exception:
        return {}
