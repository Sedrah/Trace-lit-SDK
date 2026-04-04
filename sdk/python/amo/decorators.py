from __future__ import annotations

import functools
import inspect
import random
import traceback as tb
from datetime import datetime, timezone
from typing import Any, Callable, TypeVar, overload
from uuid import uuid4

from .config import get_config
from .context import get_current_span_id, get_current_trace_id, reset_span_context, set_span_context
from .emitter import get_emitter
from .models import ErrorDetail, TraceEvent

F = TypeVar("F", bound=Callable[..., Any])


@overload
def trace(func: F) -> F: ...


@overload
def trace(
    func: None = None,
    *,
    agent_name: str | None = None,
    action: str | None = None,
    framework: str = "raw",
    model: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Callable[[F], F]: ...


def trace(
    func: F | None = None,
    *,
    agent_name: str | None = None,
    action: str | None = None,
    framework: str = "raw",
    model: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> F | Callable[[F], F]:
    """
    Decorator to trace a function as a span.

    Usage::

        @trace
        def my_agent(input: str) -> str: ...

        @trace(agent_name="researcher", action="web_search")
        async def search(query: str) -> list[str]: ...
    """

    def decorator(fn: F) -> F:
        _agent_name = agent_name or fn.__module__.split(".")[-1]
        _action = action or fn.__qualname__
        _metadata = metadata or {}

        if inspect.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await _run_async(fn, args, kwargs, _agent_name, _action, framework, model, _metadata)
            return async_wrapper  # type: ignore[return-value]
        else:
            @functools.wraps(fn)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                return _run_sync(fn, args, kwargs, _agent_name, _action, framework, model, _metadata)
            return sync_wrapper  # type: ignore[return-value]

    if func is not None:
        # Called as @trace (no parentheses)
        return decorator(func)
    # Called as @trace(...) with keyword arguments
    return decorator


# ---------------------------------------------------------------------------
# Internal execution helpers
# ---------------------------------------------------------------------------

def _should_sample() -> bool:
    rate = get_config().sampling_rate
    return rate >= 1.0 or random.random() < rate


def _begin_span(
    agent_name: str,
    action: str,
    framework: str,
    model: str | None,
    metadata: dict[str, Any],
) -> tuple[TraceEvent, float, Any, Any]:
    """
    Snapshot context, generate span IDs, set new context.
    Returns (event_partial, start_perf, trace_token, span_token).
    The event is not fully built yet — duration and status are set after execution.
    """
    parent_span_id = get_current_span_id()
    trace_id = get_current_trace_id() or uuid4()
    span_id = uuid4()

    trace_token, span_token = set_span_context(trace_id, span_id)

    event = TraceEvent(
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        timestamp=datetime.now(timezone.utc),
        framework=framework,  # type: ignore[arg-type]
        agent_name=agent_name,
        action=action,
        model=model,
        metadata=metadata,
    )
    return event, __import__("time").perf_counter(), trace_token, span_token


def _end_span(
    event: TraceEvent,
    start: float,
    exc: BaseException | None,
    trace_token: Any,
    span_token: Any,
) -> None:
    """Finalize the event and emit it. Always restores context."""
    import time

    reset_span_context(trace_token, span_token)

    duration_ms = int((time.perf_counter() - start) * 1000)

    if exc is not None:
        final = event.model_copy(
            update={
                "status": "error",
                "duration_ms": duration_ms,
                "error": ErrorDetail(
                    error_type=type(exc).__name__,
                    message=str(exc),
                    traceback=tb.format_exc(),
                ),
            }
        )
    else:
        final = event.model_copy(update={"status": "success", "duration_ms": duration_ms})

    try:
        get_emitter().emit(final)
    except Exception:
        pass  # emitter errors must never surface to the caller


def _run_sync(
    fn: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    agent_name: str,
    action: str,
    framework: str,
    model: str | None,
    metadata: dict[str, Any],
) -> Any:
    cfg = get_config()
    if cfg.disabled or not _should_sample():
        return fn(*args, **kwargs)

    event, start, trace_token, span_token = _begin_span(agent_name, action, framework, model, metadata)
    exc_captured: BaseException | None = None
    try:
        return fn(*args, **kwargs)
    except BaseException as exc:
        exc_captured = exc
        raise
    finally:
        _end_span(event, start, exc_captured, trace_token, span_token)


async def _run_async(
    fn: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    agent_name: str,
    action: str,
    framework: str,
    model: str | None,
    metadata: dict[str, Any],
) -> Any:
    cfg = get_config()
    if cfg.disabled or not _should_sample():
        return await fn(*args, **kwargs)

    event, start, trace_token, span_token = _begin_span(agent_name, action, framework, model, metadata)
    exc_captured: BaseException | None = None
    try:
        return await fn(*args, **kwargs)
    except BaseException as exc:
        exc_captured = exc
        raise
    finally:
        _end_span(event, start, exc_captured, trace_token, span_token)
