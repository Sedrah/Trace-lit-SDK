"""
LangGraph tracing helper for AMO.

LangGraph graphs are LangChain Runnables, so they accept LangChain callbacks
via RunnableConfig. This module provides a thin wrapper that auto-injects
an AmoCallbackHandler into every graph invocation.

Usage::

    from langgraph.graph import StateGraph
    from trace_lit.wrappers import with_amo_tracing

    graph = StateGraph(...).compile()
    traced_graph = with_amo_tracing(graph)

    # Now use traced_graph exactly like the original:
    result = traced_graph.invoke({"messages": [...]})
    async for chunk in traced_graph.astream({"messages": [...]}):
        ...
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Iterator

from .langchain import AmoCallbackHandler


class _AmoTracedGraph:
    """
    Delegation wrapper around a compiled LangGraph graph that injects
    AmoCallbackHandler into every invoke/stream call.
    """

    def __init__(self, graph: Any, handler: AmoCallbackHandler) -> None:
        self._graph = graph
        self._handler = handler

    def _inject(self, config: dict[str, Any] | None) -> dict[str, Any]:
        config = dict(config or {})
        callbacks = list(config.get("callbacks") or [])
        if self._handler not in callbacks:
            callbacks.append(self._handler)
        config["callbacks"] = callbacks
        return config

    def invoke(self, input: Any, config: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        return self._graph.invoke(input, self._inject(config), **kwargs)

    async def ainvoke(self, input: Any, config: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        return await self._graph.ainvoke(input, self._inject(config), **kwargs)

    def stream(
        self, input: Any, config: dict[str, Any] | None = None, **kwargs: Any
    ) -> Iterator[Any]:
        yield from self._graph.stream(input, self._inject(config), **kwargs)

    async def astream(
        self, input: Any, config: dict[str, Any] | None = None, **kwargs: Any
    ) -> AsyncIterator[Any]:
        async for chunk in self._graph.astream(input, self._inject(config), **kwargs):
            yield chunk

    def __getattr__(self, name: str) -> Any:
        # Proxy everything else to the underlying graph
        return getattr(self._graph, name)


def with_amo_tracing(
    graph: Any,
    handler: AmoCallbackHandler | None = None,
) -> _AmoTracedGraph:
    """
    Wrap a compiled LangGraph graph to automatically trace all executions with AMO.

    Args:
        graph: A compiled LangGraph graph (result of StateGraph(...).compile()).
        handler: Optional existing AmoCallbackHandler. A new one is created if not provided.

    Returns:
        A wrapped graph with the same invoke/stream/ainvoke/astream interface.

    Example::

        traced = with_amo_tracing(graph)
        result = traced.invoke({"messages": [HumanMessage(content="hello")]})
    """
    return _AmoTracedGraph(graph, handler or AmoCallbackHandler())
