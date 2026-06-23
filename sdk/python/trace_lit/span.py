"""
trace_span — context manager for tracing individual steps inside a function.

Works for both sync and async code. Automatically inherits the current
trace_id and parent_span_id from the enclosing @trace decorator context.

Usage::

    from trace_lit import trace_span

    def my_agent(query: str) -> str:
        with trace_span("llm_call", model="gpt-4o") as span:
            response = client.chat.completions.create(...)
            span.set_tokens(
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
            )
        return response.choices[0].message.content

    async def async_agent(query: str) -> str:
        async with trace_span("llm_call", model="gpt-4o") as span:
            response = await async_client.chat.completions.create(...)
            span.set_tokens(
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
            )
        return response.choices[0].message.content
"""

from __future__ import annotations

import time
import traceback as tb
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .config import get_config
from .context import get_current_agent_name, get_current_span_id, get_current_trace_id, reset_span_context, set_span_context
from .emitter import get_emitter
from .models import ErrorDetail, TraceEvent


class SpanHandle:
    """Returned by trace_span — call set_tokens() or set_cost() inside the block."""

    def __init__(self) -> None:
        self._tokens: dict[str, int] = {}
        self._cost: float | None = None
        self._metadata: dict[str, Any] = {}
        self._prompt_name: str = ""
        self._prompt_content: str | None = None
        self._input_text: str | None = None
        self._output_text: str | None = None

    def set_tokens(self, input_tokens: int = 0, output_tokens: int = 0) -> None:
        self._tokens = {"input_tokens": input_tokens, "output_tokens": output_tokens}

    def set_cost(self, cost_usd: float) -> None:
        self._cost = cost_usd

    def set_metadata(self, **kwargs: Any) -> None:
        self._metadata.update(kwargs)

    def set_prompt(self, name: str, content: str) -> None:
        """Tag this span with a named prompt. Version is detected automatically
        server-side from the content — no need to track version numbers yourself."""
        self._prompt_name = name
        self._prompt_content = content

    def set_input(self, text: str) -> None:
        """Capture the input sent to this step (e.g. the prompt messages).
        Only stored when capture_io=True in SDK config — no-op otherwise."""
        if get_config().capture_io:
            self._input_text = text

    def set_output(self, text: str) -> None:
        """Capture the output from this step (e.g. the model completion).
        Only stored when capture_io=True in SDK config — no-op otherwise."""
        if get_config().capture_io:
            self._output_text = text


class trace_span:
    """
    Context manager that emits a span on exit.

    Supports both ``with`` and ``async with``.
    """

    def __init__(
        self,
        action: str,
        *,
        agent_name: str | None = None,
        model: str | None = None,
        framework: str = "raw",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._action = action
        self._agent_name = agent_name
        self._model = model
        self._framework = framework
        self._metadata = metadata or {}
        self._handle = SpanHandle()
        self._event: TraceEvent | None = None
        self._start: float = 0.0
        self._trace_token: Any = None
        self._span_token: Any = None
        self._agent_token: Any = None
        self._disabled = False

    def _enter(self) -> SpanHandle:
        cfg = get_config()
        if cfg.disabled:
            self._disabled = True
            return self._handle

        parent_span_id = get_current_span_id()
        trace_id = get_current_trace_id() or uuid4()
        span_id = uuid4()
        resolved_agent = self._agent_name or get_current_agent_name() or "unknown"

        self._trace_token, self._span_token, self._agent_token = set_span_context(
            trace_id, span_id, resolved_agent
        )
        self._start = time.perf_counter()

        self._event = TraceEvent(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            timestamp=datetime.now(timezone.utc),
            framework=self._framework,  # type: ignore[arg-type]
            agent_name=resolved_agent,
            action=self._action,
            model=self._model,
            metadata=self._metadata,
        )
        return self._handle

    def _exit(self, exc: BaseException | None) -> None:
        if self._disabled or self._event is None:
            return

        reset_span_context(self._trace_token, self._span_token, self._agent_token)
        duration_ms = int((time.perf_counter() - self._start) * 1000)

        extra: dict[str, Any] = {
            "duration_ms": duration_ms,
            **self._handle._tokens,
            "metadata": {**self._event.metadata, **self._handle._metadata},
        }
        if self._handle._cost is not None:
            extra["cost_usd"] = self._handle._cost
        if self._handle._prompt_name:
            extra["prompt_name"] = self._handle._prompt_name
            extra["prompt_content"] = self._handle._prompt_content
        if self._handle._input_text is not None:
            extra["input_text"] = self._handle._input_text
        if self._handle._output_text is not None:
            extra["output_text"] = self._handle._output_text

        if exc is not None:
            extra["status"] = "error"
            extra["error"] = ErrorDetail(
                error_type=type(exc).__name__,
                message=str(exc),
                traceback=tb.format_exc(),
            )
        else:
            extra["status"] = "success"

        final = self._event.model_copy(update=extra)
        try:
            get_emitter().emit(final)
        except Exception:
            pass

    # Sync context manager
    def __enter__(self) -> SpanHandle:
        return self._enter()

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._exit(exc_val)

    # Async context manager
    async def __aenter__(self) -> SpanHandle:
        return self._enter()

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._exit(exc_val)
