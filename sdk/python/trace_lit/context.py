from __future__ import annotations

from contextvars import ContextVar, Token
from uuid import UUID

# ContextVar propagates automatically across asyncio tasks and sync call stacks.
# Each async task gets its own copy, so concurrent traces don't interfere.
_current_trace_id: ContextVar[UUID | None] = ContextVar("amo_trace_id", default=None)
_current_span_id: ContextVar[UUID | None] = ContextVar("amo_span_id", default=None)


def get_current_trace_id() -> UUID | None:
    return _current_trace_id.get()


def get_current_span_id() -> UUID | None:
    return _current_span_id.get()


def set_span_context(trace_id: UUID, span_id: UUID) -> tuple[Token[UUID | None], Token[UUID | None]]:
    """Set the current trace/span context. Returns tokens to restore the previous context."""
    trace_token = _current_trace_id.set(trace_id)
    span_token = _current_span_id.set(span_id)
    return trace_token, span_token


def reset_span_context(
    trace_token: Token[UUID | None],
    span_token: Token[UUID | None],
) -> None:
    """Restore the context that existed before set_span_context was called."""
    _current_trace_id.reset(trace_token)
    _current_span_id.reset(span_token)
