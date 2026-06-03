"""
Auto-patching for LLM client libraries.

Usage::

    import trace_lit
    trace_lit.autopatch()           # patches everything available
    trace_lit.patch_openai()        # OpenAI only
    trace_lit.patch_anthropic()     # Anthropic only

All functions are idempotent and silently skip libraries that are not installed.
Works for both openai.OpenAI / AsyncOpenAI and Ollama/vLLM/any OpenAI-compatible
client since they use the same openai package.
"""
from __future__ import annotations


def patch_openai() -> bool:
    """Patch the openai client. Returns True if patched, False if not installed."""
    from ._openai import patch_openai as _p
    return _p()


def patch_anthropic() -> bool:
    """Patch the anthropic client. Returns True if patched, False if not installed."""
    from ._anthropic import patch_anthropic as _p
    return _p()


def autopatch() -> dict[str, bool]:
    """
    Patch all supported LLM clients that are currently installed.

    Returns a dict of {library: patched} so callers can see what was found::

        {"openai": True, "anthropic": False}
    """
    return {
        "openai":    patch_openai(),
        "anthropic": patch_anthropic(),
    }
