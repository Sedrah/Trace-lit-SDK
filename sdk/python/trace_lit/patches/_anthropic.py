"""
Auto-patch for anthropic.Anthropic / anthropic.AsyncAnthropic.

Wraps every messages.create call in a trace_span that captures:
  - model name
  - input / output token counts  (non-streaming; streaming support is TODO)
  - exceptions raised by the API

Streaming: for stream=True calls, only the model name is captured.
Use trace_span() manually with set_tokens() if you need token counts
for streaming responses.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("trace_lit")

_patched = False


def patch_anthropic() -> bool:
    """
    Patch anthropic.resources.messages.messages.Messages.create (sync + async).

    Returns True if patched, False if anthropic is not installed.
    Idempotent — safe to call multiple times.
    """
    global _patched
    if _patched:
        return True

    try:
        import anthropic.resources.messages.messages as _m
    except ImportError:
        return False

    from ..span import trace_span

    _orig_sync  = _m.Messages.create
    _orig_async = _m.AsyncMessages.create

    def _sync_create(self: Any, **kwargs: Any) -> Any:
        model  = str(kwargs.get("model", "unknown"))
        stream = bool(kwargs.get("stream", False))

        span_cm = trace_span("llm_call", model=model)
        handle  = span_cm._enter()

        try:
            response = _orig_sync(self, **kwargs)
        except BaseException as exc:
            span_cm._exit(exc)
            raise

        if not stream:
            _grab_anthropic_tokens(handle, response)
            _grab_anthropic_io(handle, kwargs, response)
            span_cm._exit(None)
        else:
            # Streaming: emit span with model name only; tokens are not yet available
            handle.set_metadata(streaming=True)
            span_cm._exit(None)

        return response

    async def _async_create(self: Any, **kwargs: Any) -> Any:
        model  = str(kwargs.get("model", "unknown"))
        stream = bool(kwargs.get("stream", False))

        span_cm = trace_span("llm_call", model=model)
        handle  = span_cm._enter()

        try:
            response = await _orig_async(self, **kwargs)
        except BaseException as exc:
            span_cm._exit(exc)
            raise

        if not stream:
            _grab_anthropic_tokens(handle, response)
            _grab_anthropic_io(handle, kwargs, response)
            span_cm._exit(None)
        else:
            handle.set_metadata(streaming=True)
            span_cm._exit(None)

        return response

    _m.Messages.create      = _sync_create
    _m.AsyncMessages.create = _async_create
    _patched = True
    logger.info("trace_lit: anthropic patched")
    return True


def _grab_anthropic_io(handle: Any, kwargs: Any, response: Any) -> None:
    import json
    messages = kwargs.get("messages")
    if messages:
        try:
            handle.set_input(json.dumps(messages, ensure_ascii=False))
        except Exception:
            pass
    try:
        block = response.content[0]
        text = getattr(block, "text", None)
        if text:
            handle.set_output(text)
    except Exception:
        pass


def _grab_anthropic_tokens(handle: Any, response: Any) -> None:
    usage = getattr(response, "usage", None)
    if usage:
        handle.set_tokens(
            input_tokens=int(getattr(usage, "input_tokens",  0) or 0),
            output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
        )
