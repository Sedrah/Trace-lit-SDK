# Trace-lit

Observability for multi-agent AI pipelines — cost, failures, and execution graphs in a dashboard built for non-developers.

![Overview](docs/screenshots/overview.png)

---

## Quickstart

**1. Create a free account**

Go to [app.trace-lit.com/signup](https://app.trace-lit.com/signup), enter your email, and click the verification link. Then go to **Settings → Create key** to get your API key.

**2. Install the SDK**

```bash
pip install tracelit-sdk
```

**3. Instrument your agent**

```python
import trace_lit

trace_lit.configure(
    kafka_brokers=["app.trace-lit.com:9093"],
    api_key="YOUR_API_KEY",   # from Settings → Create key
)

@trace_lit.trace(agent_name="my-agent")
def run(query):
    # your agent code — no other changes needed
    ...
```

Run your agent. Traces appear in the dashboard automatically.

**4. Test the connection**

```bash
python3 -m trace_lit.quickstart \
  --broker app.trace-lit.com:9093 \
  --key YOUR_API_KEY
# ✓ Connected to Trace-lit
# ✓ Test trace sent
# ✓ View at https://app.trace-lit.com
```

---

**[Open dashboard →](https://app.trace-lit.com)**

---

## What you get

Every agent run is captured automatically — cost, failures, and the full execution graph.

![Traces](docs/screenshots/traces.png)

Failures are classified in plain English, not error codes.

![Failures](docs/screenshots/failures.png)

Click any trace to see the execution graph and step timeline.

![Trace detail](docs/screenshots/trace_detail.png)

---

## Framework integrations

Works out of the box with LangChain, LangGraph, CrewAI, and any OpenAI/Anthropic client via auto-patching:

```python
trace_lit.autopatch()   # auto-captures model, tokens, and cost from openai/anthropic calls
```

OpenTelemetry-compatible agents are also supported — point your OTLP exporter at `https://app.trace-lit.com/otlp/v1/traces`.

---

## Self-hosting

```bash
git clone https://github.com/Sedrah/Trace-lit-SDK
cd Trace-lit-SDK
docker compose -f infra/docker-compose.yml up -d
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full stack diagram.

---

**Community** — [GitHub](https://github.com/Sedrah/Trace-lit-SDK) · [contact us](mailto:hello@trace-lit.com)

MIT License
