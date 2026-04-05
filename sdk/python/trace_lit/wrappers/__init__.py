"""
AMO framework wrappers.

Lazy imports — framework packages are only loaded when the wrapper is accessed,
so `import amo` never fails even if LangChain or CrewAI are not installed.

Usage::

    from trace_lit.wrappers import AmoCallbackHandler      # LangChain / LangGraph
    from trace_lit.wrappers import with_amo_tracing        # LangGraph graph helper
    from trace_lit.wrappers import AmoCrewWrapper          # CrewAI
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .crewai import AmoCrewWrapper
    from .langchain import AmoCallbackHandler
    from .langgraph import with_amo_tracing


def __getattr__(name: str) -> object:
    if name == "AmoCallbackHandler":
        from .langchain import AmoCallbackHandler
        return AmoCallbackHandler
    if name == "with_amo_tracing":
        from .langgraph import with_amo_tracing
        return with_amo_tracing
    if name == "AmoCrewWrapper":
        from .crewai import AmoCrewWrapper
        return AmoCrewWrapper
    raise AttributeError(f"module 'amo.wrappers' has no attribute {name!r}")


__all__ = ["AmoCallbackHandler", "with_amo_tracing", "AmoCrewWrapper"]
