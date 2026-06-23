# examples/fake_agent.py
#
# Demonstrates three features:
#
# 1. AUTO-PATCHING — trace_lit.autopatch() intercepts every openai/anthropic
#    call automatically. No manual set_tokens() needed.
#
# 2. INTERNAL VISIBILITY — trace_span() shows individual LLM calls and tool
#    calls as child spans inside an agent function, with token counts.
#
# 3. FAILURE ATTRIBUTION — the server classifies root causes and cascades.

import os
import time
from unittest.mock import MagicMock

import trace_lit as amo
from trace_lit import trace_span

amo.configure(
    kafka_brokers=["app.trace-lit.com:9093"],
    api_key=os.environ.get("TRACELIT_API_KEY", "sk-demo-abc123"),
)


# ---------------------------------------------------------------------------
# AUTO-PATCHING DEMO
#
# autopatch() wraps the openai client so every LLM call emits a span with
# model + tokens automatically. No trace_span, no set_tokens() — zero code.
#
# We mock the openai response here so no real API key is needed.
# In production: remove the mock, add your real OPENAI_API_KEY.
# ---------------------------------------------------------------------------

def _fake_openai_response(prompt_tokens: int, completion_tokens: int) -> MagicMock:
    r = MagicMock()
    r.usage.prompt_tokens     = prompt_tokens
    r.usage.completion_tokens = completion_tokens
    r.choices[0].message.content = "Fake LLM response"
    return r


def demo_autopatch() -> None:
    # Patch the openai client before autopatching so no real API call is made
    import openai.resources.chat.completions.completions as _cc
    _cc.Completions.create = lambda _, **kw: _fake_openai_response(
        prompt_tokens=int(kw.get("max_tokens", 200) * 1.5),
        completion_tokens=int(kw.get("max_tokens", 200)),
    )

    result = amo.autopatch()
    print(f"  autopatch result: {result}")   # {"openai": True, "anthropic": False/True}

    # From here: any call to client.chat.completions.create() is automatically traced.
    # The span captures model name + tokens with zero extra code.
    import openai
    client = openai.OpenAI(api_key="sk-fake-key-for-demo-only")

    @amo.trace(agent_name="autopatch-demo", framework="raw")
    def run_pipeline(query: str) -> str:
        # Call 1 — planning step
        client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": f"Plan how to answer: {query}"}],
            max_tokens=100,
        )
        # Call 2 — answer step, bigger model
        client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": query}],
            max_tokens=400,
        )
        return "done"

    run_pipeline("What is the future of grid energy AI?")
    print("  autopatch trace emitted — look for 'autopatch-demo' in dashboard")


# ---------------------------------------------------------------------------
# Happy-path pipeline — shows internal visibility with trace_span
# ---------------------------------------------------------------------------

@amo.trace(agent_name="research-agent", framework="langchain")
def research_pipeline(query: str) -> str:
    # Step 1: plan the query — small model, low cost
    with trace_span("plan_research", model="gpt-4o-mini") as span:
        time.sleep(0.04)
        span.set_tokens(input_tokens=110, output_tokens=35)

    # Step 2: run web search tool
    with trace_span("web_search") as span:
        time.sleep(0.07)
        span.set_metadata(results_count=8, query=query)

    # Step 3: synthesise — large model, more tokens
    with trace_span("synthesise_results", model="gpt-4o") as span:
        time.sleep(0.09)
        span.set_tokens(input_tokens=850, output_tokens=380)

    return f"Research results for: {query}"


@amo.trace(agent_name="writer-agent", framework="crewai")
def write_pipeline(research: str) -> str:
    # Step 1: outline structure
    with trace_span("create_outline", model="gpt-4o-mini") as span:
        time.sleep(0.04)
        span.set_tokens(input_tokens=190, output_tokens=75)

    # Step 2: write the report — Claude, longer output
    with trace_span("write_report", model="claude-3-5-sonnet-20241022") as span:
        time.sleep(0.11)
        span.set_tokens(input_tokens=620, output_tokens=420)

    return f"Report: {research[:80]}"


# ---------------------------------------------------------------------------
# Failure scenario A — tool returns empty → root cause + intra-agent cascade
#
# Attribution result:
#   Root cause:  market-data-agent / fetch_market_data
#                classification: tool_empty_result
#                "Tool returned an empty result"
#   Cascade:     call_market_api inner span (parent failed)
# ---------------------------------------------------------------------------

@amo.trace(agent_name="market-data-agent", action="fetch_market_data", framework="langchain")
def failing_tool_pipeline(symbol: str) -> str:
    # Successful planning step — shows up as green child span
    with trace_span("plan_query", model="gpt-4o-mini") as span:
        time.sleep(0.04)
        span.set_tokens(input_tokens=70, output_tokens=22)

    # Tool call that returns nothing — this is the root cause
    with trace_span("call_market_api") as span:
        time.sleep(0.09)
        raise ValueError(
            "Tool returned empty result — market API returned 0 records for " + symbol
        )

    return "never reached"  # noqa: unreachable


# ---------------------------------------------------------------------------
# Failure scenario B — LLM timeout
#
# Attribution result:
#   Root cause:  summariser-agent / summarise
#                classification: llm_timeout
#                "LLM did not respond in time"
#   Cascade:     llm_call inner span (parent failed)
# ---------------------------------------------------------------------------

@amo.trace(agent_name="summariser-agent", action="summarise", framework="langchain")
def failing_timeout_pipeline(_text: str) -> str:
    with trace_span("llm_call", model="gpt-4o") as span:
        time.sleep(0.08)
        raise TimeoutError("OpenAI API did not respond within 30s — request abandoned")

    return "never reached"  # noqa: unreachable


# ---------------------------------------------------------------------------
# Failure scenario C — rate limit, with a prior successful step to show
#                       mixed internal visibility in the same trace
#
# Attribution result:
#   Root cause:  enrichment-agent / enrich_entity
#                classification: rate_limit
#                "LLM API rate limit exceeded"
#   Cascade:     enrich_llm_call inner span (parent failed)
# ---------------------------------------------------------------------------

@amo.trace(agent_name="enrichment-agent", action="enrich_entity", framework="langgraph")
def failing_rate_limit_pipeline(entity: str) -> str:
    # First step succeeds — mixed trace shows green + red in DAG
    with trace_span("lookup_entity_db") as span:
        time.sleep(0.03)
        span.set_metadata(entity=entity, found=True)

    # Second step hits rate limit
    with trace_span("enrich_llm_call", model="gpt-4o") as span:
        time.sleep(0.05)
        raise RuntimeError("Rate limit exceeded — 429 Too Many Requests from OpenAI")

    return "never reached"  # noqa: unreachable


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Auto-patching demo — tokens captured automatically, no set_tokens()
    print("--- autopatch demo ---")
    demo_autopatch()
    time.sleep(0.5)

    # Happy-path traces — demonstrate internal visibility
    print("--- internal visibility demo ---")
    for i in range(4):
        r = research_pipeline(f"AI agent use case {i + 1}")
        write_pipeline(r)
        print(f"Happy-path trace {i + 1} emitted")

    time.sleep(0.5)

    # Failure traces — demonstrate attribution
    try:
        failing_tool_pipeline("AAPL")
    except Exception:
        pass
    print("Failure A emitted (tool_empty_result + cascade)")

    try:
        failing_timeout_pipeline("Summarise quarterly earnings report...")
    except Exception:
        pass
    print("Failure B emitted (llm_timeout)")

    try:
        failing_rate_limit_pipeline("OpenAI Inc.")
    except Exception:
        pass
    print("Failure C emitted (rate_limit, mixed trace)")

    time.sleep(3)
    print("Done. Open any red trace in the dashboard to see failure attribution.")
