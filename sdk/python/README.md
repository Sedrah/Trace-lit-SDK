# Tracelit SDK

Python SDK for Trace-lit — instrument AI agents with one decorator.

## Install

```bash
pip install "tracelit-sdk[kafka]"
```

For LangChain / LangGraph:
```bash
pip install "tracelit-sdk[all-langchain]"
```

For CrewAI:
```bash
pip install "tracelit-sdk[all-crewai]"
```

> **Note:** `crewai` and `langgraph` have a hard pip version conflict — never install `[all-langchain]` and `[all-crewai]` in the same environment.

## Usage

```python
import trace_lit

trace_lit.configure(
    kafka_brokers=["49.13.235.169:9093"],
    api_key="your-api-key",
)

@trace_lit.trace(agent_name="my-agent", framework="langchain")
def my_agent(query: str) -> str:
    ...
```

## Development

```bash
pip install -e ".[dev]"
pytest -v
```
