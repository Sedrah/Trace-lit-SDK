"""
Auto-patch for openai.OpenAI / openai.AsyncOpenAI.

Wraps every chat.completions.create call in a trace_span that captures:
  - model name
  - input / output token counts  (non-streaming and streaming best-effort)
  - exceptions raised by the API

Streaming: the response is wrapped in a thin proxy that reads token counts
from any chunk that carries usage data (available when the caller passes
stream_options={"include_usage": True}, or when the server emits it anyway).
No tokens are counted for streams that are abandoned before exhaustion.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("trace_lit")

_patched = False


def patch_openai() -> bool:
    """
    Patch openai.resources.chat.completions.Completions.create (sync + async).

    Returns True if patched, False if openai is not installed.
    Idempotent — safe to call multiple times.
    """
    global _patched
    if _patched:
        return True

    try:
        import openai.resources.chat.completions.completions as _m
    except ImportError:
        return False

    from ..span import trace_span

    _orig_sync  = _m.Completions.create
    _orig_async = _m.AsyncCompletions.create

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
            _grab_openai_tokens(handle, response)
            span_cm._exit(None)
            return response

        # Return a proxy that finalises the span when the stream is consumed
        return _SyncStreamProxy(response, span_cm, handle)

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
            _grab_openai_tokens(handle, response)
            span_cm._exit(None)
            return response

        return _AsyncStreamProxy(response, span_cm, handle)

    _m.Completions.create      = _sync_create
    _m.AsyncCompletions.create = _async_create
    _patched = True
    logger.info("trace_lit: openai patched")
    return True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _grab_openai_tokens(handle: Any, response: Any) -> None:
    usage = getattr(response, "usage", None)
    if usage:
        handle.set_tokens(
            input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
        )


class _SyncStreamProxy:
    """Wraps a sync OpenAI stream; finalises the span when iteration ends."""

    __slots__ = ("_stream", "_span_cm", "_handle", "_input", "_output")

    def __init__(self, stream: Any, span_cm: Any, handle: Any) -> None:
        self._stream  = stream
        self._span_cm = span_cm
        self._handle  = handle
        self._input   = 0
        self._output  = 0

    # Context-manager support (common pattern: `with client.chat... as s:`)
    def __enter__(self) -> "_SyncStreamProxy":
        if hasattr(self._stream, "__enter__"):
            self._stream.__enter__()
        return self

    def __exit__(self, *args: Any) -> Any:
        result = None
        if hasattr(self._stream, "__exit__"):
            result = self._stream.__exit__(*args)
        exc = args[1]
        self._finalise(exc)
        return result

    def __iter__(self):  # type: ignore[override]
        try:
            for chunk in self._stream:
                self._check_usage(chunk)
                yield chunk
            self._finalise(None)
        except BaseException as exc:
            self._finalise(exc)
            raise

    def _check_usage(self, chunk: Any) -> None:
        usage = getattr(chunk, "usage", None)
        if usage:
            self._input  = int(getattr(usage, "prompt_tokens",     0) or 0)
            self._output = int(getattr(usage, "completion_tokens", 0) or 0)

    def _finalise(self, exc: Any) -> None:
        if self._input or self._output:
            self._handle.set_tokens(input_tokens=self._input, output_tokens=self._output)
        self._span_cm._exit(exc)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._stream, name)


class _AsyncStreamProxy:
    """Wraps an async OpenAI stream; finalises the span when iteration ends."""

    __slots__ = ("_stream", "_span_cm", "_handle", "_input", "_output")

    def __init__(self, stream: Any, span_cm: Any, handle: Any) -> None:
        self._stream  = stream
        self._span_cm = span_cm
        self._handle  = handle
        self._input   = 0
        self._output  = 0

    async def __aenter__(self) -> "_AsyncStreamProxy":
        if hasattr(self._stream, "__aenter__"):
            await self._stream.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> Any:
        result = None
        if hasattr(self._stream, "__aexit__"):
            result = await self._stream.__aexit__(*args)
        exc = args[1]
        self._finalise(exc)
        return result

    async def __aiter__(self):  # type: ignore[override]
        try:
            async for chunk in self._stream:
                self._check_usage(chunk)
                yield chunk
            self._finalise(None)
        except BaseException as exc:
            self._finalise(exc)
            raise

    def _check_usage(self, chunk: Any) -> None:
        usage = getattr(chunk, "usage", None)
        if usage:
            self._input  = int(getattr(usage, "prompt_tokens",     0) or 0)
            self._output = int(getattr(usage, "completion_tokens", 0) or 0)

    def _finalise(self, exc: Any) -> None:
        if self._input or self._output:
            self._handle.set_tokens(input_tokens=self._input, output_tokens=self._output)
        self._span_cm._exit(exc)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._stream, name)
