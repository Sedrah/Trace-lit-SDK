"""
LangChain callback handler for AMO tracing.

Captures LLM calls, tool calls, and chain executions, including token counts
where the LLM provider exposes them.

Usage::

    from amo.wrappers import AmoCallbackHandler

    handler = AmoCallbackHandler()

    # Pass to any LangChain chain/agent
    result = chain.invoke({"input": "..."}, config={"callbacks": [handler]})
"""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from ..emitter import get_emitter
from ..models import ErrorDetail, TraceEvent


class AmoCallbackHandler(BaseCallbackHandler):
    """
    LangChain callback handler that emits AMO trace events for every LLM call,
    tool call, and chain execution.

    One instance can be shared across multiple invocations — it is thread-safe
    because each run_id is scoped to a single concurrent execution.
    """

    def __init__(self) -> None:
        super().__init__()
        # run_id → (partial_event, start_perf_counter)
        self._pending: dict[UUID, tuple[TraceEvent, float]] = {}

    # ------------------------------------------------------------------
    # LLM
    # ------------------------------------------------------------------

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        agent_name = _extract_name(serialized, default="llm")
        model = _extract_model(serialized, kwargs)
        event = TraceEvent(
            parent_span_id=parent_run_id,
            framework="langchain",
            agent_name=agent_name,
            action="llm_call",
            model=model,
        )
        self._pending[run_id] = (event, time.perf_counter())

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        event, start = self._pending.pop(run_id, (None, None))
        if event is None:
            return

        usage = _extract_token_usage(response)
        final = event.model_copy(
            update={
                "span_id": run_id,
                "status": "success",
                "duration_ms": int((time.perf_counter() - start) * 1000),
                **usage,
            }
        )
        get_emitter().emit(final)

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        self._emit_error(run_id, error, action="llm_call")

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        tool_name = _extract_name(serialized, default="tool")
        event = TraceEvent(
            parent_span_id=parent_run_id,
            framework="langchain",
            agent_name=tool_name,
            action="tool_call",
            metadata={"input": input_str[:500]},  # cap metadata size
        )
        self._pending[run_id] = (event, time.perf_counter())

    def on_tool_end(
        self,
        output: str,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        event, start = self._pending.pop(run_id, (None, None))
        if event is None:
            return
        final = event.model_copy(
            update={
                "span_id": run_id,
                "status": "success",
                "duration_ms": int((time.perf_counter() - start) * 1000),
                "metadata": {**event.metadata, "output_length": len(output)},
            }
        )
        get_emitter().emit(final)

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        self._emit_error(run_id, error, action="tool_call")

    # ------------------------------------------------------------------
    # Chains (root spans — wrap the overall agent execution)
    # ------------------------------------------------------------------

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        chain_name = _extract_name(serialized, default="chain")
        event = TraceEvent(
            parent_span_id=parent_run_id,
            framework="langchain",
            agent_name=chain_name,
            action="chain_run",
        )
        self._pending[run_id] = (event, time.perf_counter())

    def on_chain_end(
        self,
        outputs: dict[str, Any],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        event, start = self._pending.pop(run_id, (None, None))
        if event is None:
            return
        final = event.model_copy(
            update={
                "span_id": run_id,
                "status": "success",
                "duration_ms": int((time.perf_counter() - start) * 1000),
            }
        )
        get_emitter().emit(final)

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        self._emit_error(run_id, error, action="chain_run")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _emit_error(self, run_id: UUID, error: BaseException, action: str) -> None:
        entry = self._pending.pop(run_id, None)
        if entry is None:
            return
        event, start = entry
        final = event.model_copy(
            update={
                "span_id": run_id,
                "status": "error",
                "duration_ms": int((time.perf_counter() - start) * 1000),
                "action": action,
                "error": ErrorDetail(
                    error_type=type(error).__name__,
                    message=str(error),
                ),
            }
        )
        get_emitter().emit(final)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_name(serialized: dict[str, Any], default: str) -> str:
    """Pull a human-readable name from a LangChain serialized object."""
    if "name" in serialized:
        return str(serialized["name"])
    if "id" in serialized and isinstance(serialized["id"], list):
        return str(serialized["id"][-1])
    return default


def _extract_model(serialized: dict[str, Any], kwargs: dict[str, Any]) -> str | None:
    """Try to extract the model name from the serialized LLM dict."""
    for key in ("model_name", "model", "model_id"):
        val = serialized.get("kwargs", {}).get(key) or serialized.get(key)
        if val:
            return str(val)
    return kwargs.get("invocation_params", {}).get("model_name")


def _extract_token_usage(response: LLMResult) -> dict[str, Any]:
    """
    Extract token usage from an LLMResult. LLM providers use different field names
    so we try several common patterns and fall back to zeros.
    """
    usage = (response.llm_output or {}).get("token_usage") or {}
    if not usage:
        # Some providers put usage at the generation level
        for gen_list in response.generations:
            for gen in gen_list:
                info = getattr(gen, "generation_info", {}) or {}
                if "usage" in info:
                    usage = info["usage"]
                    break

    return {
        "input_tokens": int(
            usage.get("prompt_tokens")
            or usage.get("input_tokens")
            or usage.get("prompt_token_count")
            or 0
        ),
        "output_tokens": int(
            usage.get("completion_tokens")
            or usage.get("output_tokens")
            or usage.get("candidates_token_count")
            or 0
        ),
    }
