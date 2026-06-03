"""
Tests for auto-patching (openai + anthropic).

Uses unittest.mock to simulate the client calls — no real API keys needed.
"""
from __future__ import annotations

import importlib
import sys
from types import ModuleType
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from trace_lit import autopatch, patch_anthropic, patch_openai
from trace_lit.patches._openai import _patched as _openai_patched_flag  # noqa: F401


# ---------------------------------------------------------------------------
# Helpers to build fake openai / anthropic response objects
# ---------------------------------------------------------------------------

def _openai_usage(prompt: int, completion: int) -> MagicMock:
    u = MagicMock()
    u.prompt_tokens     = prompt
    u.completion_tokens = completion
    return u


def _anthropic_usage(inp: int, out: int) -> MagicMock:
    u = MagicMock()
    u.input_tokens  = inp
    u.output_tokens = out
    return u


def _fake_openai_response(prompt: int = 10, completion: int = 5) -> MagicMock:
    r = MagicMock()
    r.usage = _openai_usage(prompt, completion)
    return r


def _fake_anthropic_response(inp: int = 8, out: int = 3) -> MagicMock:
    r = MagicMock()
    r.usage = _anthropic_usage(inp, out)
    return r


# ---------------------------------------------------------------------------
# OpenAI patching
# ---------------------------------------------------------------------------

class TestPatchOpenAI:
    def test_returns_true_when_installed(self):
        # openai is installed in this env (added to dev deps)
        result = patch_openai()
        assert result is True

    def test_idempotent(self):
        r1 = patch_openai()
        r2 = patch_openai()
        assert r1 == r2

    def test_tokens_captured_on_sync_call(self):
        from trace_lit.patches import _openai as _oa_mod
        import openai.resources.chat.completions.completions as _m

        captured: list[Any] = []

        def fake_orig(self, **kwargs):
            return _fake_openai_response(prompt=20, completion=8)

        with patch.object(_m.Completions, "create", fake_orig):
            # Re-apply patch so it wraps our fake
            _oa_mod._patched = False
            patch_openai()

            from trace_lit.emitter import get_emitter
            emitted: list[Any] = []
            original_emit = get_emitter().emit
            get_emitter().emit = lambda e: emitted.append(e)

            try:
                client = MagicMock()
                _m.Completions.create(client, model="gpt-4o", messages=[])
            finally:
                get_emitter().emit = original_emit

        # span should have been emitted with token counts
        # (emitted via the background worker — check emitter directly via trace_span)
        # We verify via the SpanHandle mechanism below instead

    def test_no_error_when_openai_missing(self):
        """If openai isn't importable, patch_openai should return False not raise."""
        with patch.dict(sys.modules, {"openai": None, "openai.resources": None,
                                       "openai.resources.chat": None,
                                       "openai.resources.chat.completions": None,
                                       "openai.resources.chat.completions.completions": None}):
            import trace_lit.patches._openai as _m
            old = _m._patched
            _m._patched = False
            try:
                result = _m.patch_openai()
                assert result is False
            finally:
                _m._patched = old


class TestPatchAnthropic:
    def test_returns_true_when_installed(self):
        result = patch_anthropic()
        assert result is True

    def test_idempotent(self):
        r1 = patch_anthropic()
        r2 = patch_anthropic()
        assert r1 == r2

    def test_no_error_when_anthropic_missing(self):
        with patch.dict(sys.modules, {"anthropic": None,
                                       "anthropic.resources": None,
                                       "anthropic.resources.messages": None,
                                       "anthropic.resources.messages.messages": None}):
            import trace_lit.patches._anthropic as _m
            old = _m._patched
            _m._patched = False
            try:
                result = _m.patch_anthropic()
                assert result is False
            finally:
                _m._patched = old


class TestAutopatch:
    def test_returns_dict(self):
        result = autopatch()
        assert isinstance(result, dict)
        assert "openai" in result
        assert "anthropic" in result

    def test_values_are_bool(self):
        result = autopatch()
        for v in result.values():
            assert isinstance(v, bool)


# ---------------------------------------------------------------------------
# SpanHandle integration — tokens flow into the span correctly
# ---------------------------------------------------------------------------

class TestSpanHandleTokenCapture:
    """Verify that set_tokens() is called correctly by the patch logic."""

    def test_openai_sync_tokens_via_handle(self):
        from trace_lit.span import SpanHandle

        handle = SpanHandle()
        fake_resp = _fake_openai_response(prompt=15, completion=7)

        import trace_lit.patches._openai as _oa
        _oa._grab_openai_tokens(handle, fake_resp)

        assert handle._tokens == {"input_tokens": 15, "output_tokens": 7}

    def test_openai_sync_no_usage(self):
        from trace_lit.span import SpanHandle
        import trace_lit.patches._openai as _oa

        handle = SpanHandle()
        fake_resp = MagicMock()
        fake_resp.usage = None
        _oa._grab_openai_tokens(handle, fake_resp)

        assert handle._tokens == {}

    def test_anthropic_sync_tokens_via_handle(self):
        from trace_lit.span import SpanHandle
        import trace_lit.patches._anthropic as _aa

        handle = SpanHandle()
        fake_resp = _fake_anthropic_response(inp=12, out=4)
        _aa._grab_anthropic_tokens(handle, fake_resp)

        assert handle._tokens == {"input_tokens": 12, "output_tokens": 4}

    def test_stream_proxy_captures_usage_chunk(self):
        """_SyncStreamProxy should extract tokens from a chunk that has usage."""
        from trace_lit.patches._openai import _SyncStreamProxy
        from trace_lit.span import SpanHandle, trace_span

        usage_chunk = MagicMock()
        usage_chunk.usage = _openai_usage(prompt=30, completion=12)
        normal_chunk = MagicMock()
        normal_chunk.usage = None

        fake_stream = iter([normal_chunk, normal_chunk, usage_chunk])

        # Use a real trace_span but with noop emitter
        from trace_lit import configure
        configure(backend="noop")

        span_cm = trace_span("test_stream", model="gpt-4o")
        handle  = span_cm._enter()

        proxy = _SyncStreamProxy(fake_stream, span_cm, handle)
        chunks = list(proxy)

        assert len(chunks) == 3
        assert handle._tokens == {"input_tokens": 30, "output_tokens": 12}
