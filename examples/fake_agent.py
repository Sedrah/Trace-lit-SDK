# examples/fake_agent.py
# Simulates a two-agent pipeline with realistic token counts so cost shows up
# in the dashboard. Uses @trace for spans that don't call LLMs, and emits
# TraceEvent directly for spans that simulate LLM calls with token counts.
# One run intentionally fails with a classified error so the Failures view
# in the dashboard has something to show.

import time
from datetime import datetime, timezone
from uuid import uuid4

import trace_lit as amo
from trace_lit.context import get_current_trace_id, get_current_span_id
from trace_lit.emitter import get_emitter
from trace_lit.models import ErrorDetail, TraceEvent

amo.configure(
    kafka_brokers=["app.trace-lit.com:9093"],
    api_key="sk-demo-abc123",
)


def emit_llm_span(
    agent_name: str,
    framework: str,
    model: str,
    action: str,
    input_tokens: int,
    output_tokens: int,
    duration_ms: int,
) -> None:
    """Emit a span that looks like a real LLM call with token counts."""
    trace_id = get_current_trace_id() or uuid4()
    parent_span_id = get_current_span_id()
    event = TraceEvent(
        trace_id=trace_id,
        span_id=uuid4(),
        parent_span_id=parent_span_id,
        timestamp=datetime.now(timezone.utc),
        framework=framework,   # type: ignore[arg-type]
        agent_name=agent_name,
        action=action,
        status="success",
        duration_ms=duration_ms,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        # cost_usd is 0 here — ingestion pipeline recalculates from tokens + model pricing
    )
    get_emitter().emit(event)


def emit_failed_span(
    agent_name: str,
    action: str,
    error_type: str,
    error_message: str,
    duration_ms: int,
) -> None:
    """Emit a span with status=error and a classified failure reason."""
    trace_id = get_current_trace_id() or uuid4()
    parent_span_id = get_current_span_id()
    event = TraceEvent(
        trace_id=trace_id,
        span_id=uuid4(),
        parent_span_id=parent_span_id,
        timestamp=datetime.now(timezone.utc),
        framework="langchain",
        agent_name=agent_name,
        action=action,
        status="error",
        duration_ms=duration_ms,
        error=ErrorDetail(
            error_type=error_type,
            message=error_message,
        ),
    )
    get_emitter().emit(event)


@amo.trace(agent_name="research-agent", framework="langchain")
def research_pipeline(query: str) -> str:
    time.sleep(0.05)
    # Simulate a GPT-4o call inside this span
    emit_llm_span(
        agent_name="research-agent",
        framework="langchain",
        model="gpt-4o",
        action="llm_call",
        input_tokens=450,
        output_tokens=120,
        duration_ms=800,
    )
    return f"Research results for: {query}"


@amo.trace(agent_name="writer-agent", framework="crewai")
def write_pipeline(research: str) -> str:
    time.sleep(0.05)
    # Simulate a Claude call inside this span
    emit_llm_span(
        agent_name="writer-agent",
        framework="crewai",
        model="claude-3-5-sonnet-20241022",
        action="llm_call",
        input_tokens=600,
        output_tokens=300,
        duration_ms=1200,
    )
    return f"Report: {research[:80]}"


@amo.trace(agent_name="research-agent", framework="langchain")
def failing_pipeline(query: str) -> None:
    time.sleep(0.05)
    # Simulate an LLM call that times out
    emit_failed_span(
        agent_name="research-agent",
        action="llm_call",
        error_type="LLM timeout",
        error_message="OpenAI API did not respond within 30s — request abandoned",
        duration_ms=30000,
    )


if __name__ == "__main__":
    for i in range(5):
        r = research_pipeline(f"AI agent use case {i}")
        write_pipeline(r)
        print(f"Trace {i + 1} emitted")

    # One intentional failure — shows up in the Failures view with a reason
    failing_pipeline("what caused the outage?")
    print("Failure trace emitted")

    time.sleep(3)  # let the batch flush before exit
    print("Done.")
