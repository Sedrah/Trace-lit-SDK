from __future__ import annotations

from contextvars import ContextVar, Token
from uuid import UUID

# ContextVar propagates automatically across asyncio tasks and sync call stacks.
# Each async task gets its own copy, so concurrent traces don't interfere.
_current_trace_id: ContextVar[UUID | None] = ContextVar("amo_trace_id", default=None)
_current_span_id: ContextVar[UUID | None] = ContextVar("amo_span_id", default=None)
_current_agent_name: ContextVar[str | None] = ContextVar("amo_agent_name", default=None)


def get_current_trace_id() -> UUID | None:
    return _current_trace_id.get()


def get_current_span_id() -> UUID | None:
    return _current_span_id.get()


def get_current_agent_name() -> str | None:
    return _current_agent_name.get()


def set_span_context(
    trace_id: UUID,
    span_id: UUID,
    agent_name: str | None = None,
) -> tuple[Token[UUID | None], Token[UUID | None], Token[str | None]]:
    """Set the current trace/span/agent context. Returns tokens to restore the previous context."""
    trace_token = _current_trace_id.set(trace_id)
    span_token = _current_span_id.set(span_id)
    agent_token = _current_agent_name.set(agent_name)
    return trace_token, span_token, agent_token


def reset_span_context(
    trace_token: Token[UUID | None],
    span_token: Token[UUID | None],
    agent_token: Token[str | None] | None = None,
) -> None:
    """Restore the context that existed before set_span_context was called."""
    _current_trace_id.reset(trace_token)
    _current_span_id.reset(span_token)
    if agent_token is not None:
        _current_agent_name.reset(agent_token)
