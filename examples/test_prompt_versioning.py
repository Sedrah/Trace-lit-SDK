# examples/test_prompt_versioning.py
#
# Demonstrates content-addressed prompt version tracking.
#
# span.set_prompt(name, content) requires no manual version number — the
# ingestion pipeline hashes the content and assigns the next sequential
# version the first time a mutation is seen for that prompt name.
#
# This script sends the same content twice (stays version 1), then a
# changed content (becomes version 2), proving versions only increment
# on an actual mutation.

import os
import time

import trace_lit as amo
from trace_lit import trace_span

amo.configure(
    kafka_brokers=["app.trace-lit.com:9093"],
    api_key=os.environ.get("TRACELIT_API_KEY", "sk-demo-abc123"),
)

PROMPT_NAME = "system-prompt-demo"

PROMPT_V1 = "You are a helpful assistant."
PROMPT_V2 = "You are a concise, helpful assistant."


@amo.trace(agent_name="prompt-versioning-demo", framework="raw")
def run_with_prompt(content: str) -> str:
    with trace_span("llm_call", model="gpt-4o-mini") as span:
        span.set_prompt(name=PROMPT_NAME, content=content)
        span.set_tokens(input_tokens=42, output_tokens=18)
        time.sleep(0.03)
    return "done"


if __name__ == "__main__":
    print("--- prompt versioning demo ---")

    # Same content twice — should both register as version 1
    run_with_prompt(PROMPT_V1)
    print(f"Sent span 1 with prompt v1 content: {PROMPT_V1!r}")

    run_with_prompt(PROMPT_V1)
    print(f"Sent span 2 with identical content — should reuse version 1")

    # Changed content — should register as version 2
    run_with_prompt(PROMPT_V2)
    print(f"Sent span 3 with mutated content: {PROMPT_V2!r} — should become version 2")

    time.sleep(2)
    amo.get_emitter().close()  # force flush before exiting

    print("\nDone. Verify in ClickHouse:")
    print(
        "  SELECT prompt_name, version, content, first_seen_at "
        "FROM trace_lit.prompt_versions "
        f"WHERE prompt_name = '{PROMPT_NAME}' ORDER BY version FORMAT Pretty"
    )
    print("Expect exactly 2 rows: version 1 and version 2.")
