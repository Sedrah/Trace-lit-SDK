# Trace-lit

Observability for multi-agent AI pipelines.

---

```bash
pip install "tracelit-sdk[kafka]"
```

```python
import trace_lit

trace_lit.configure(
    kafka_brokers=["app.trace-lit.com:9093"],
    api_key="your-key",
)

@trace_lit.trace(agent_name="my-agent", framework="langchain")
def run(query):
    ...
```

**[View dashboard →](https://app.trace-lit.com)**

---

**Get access** — [contact us](mailto:hello@trace-lit.com) or open an issue.

MIT License
