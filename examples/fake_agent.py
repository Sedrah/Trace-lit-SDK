# examples/fake_agent.py
import time
import amo

amo.configure(
    kafka_brokers=["localhost:9092"],  # must be a list, not a string
    api_key="dev-key",                 # maps to org "default" via AMO_API_KEYS
)

@amo.trace(agent_name="research-agent", framework="langchain")
def search_web(query: str) -> str:
    time.sleep(0.1)              # simulate latency
    return f"Results for: {query}"

@amo.trace(agent_name="research-agent", framework="langchain")
def summarise(text: str) -> str:
    time.sleep(0.05)
    return f"Summary: {text[:50]}"

@amo.trace(agent_name="writer-agent", framework="crewai")
def write_report(summary: str) -> str:
    time.sleep(0.2)
    return f"Report: {summary}"

if __name__ == "__main__":
    for i in range(5):           # emit 5 traces
        result = search_web(f"AI agents use case {i}")
        s = summarise(result)
        write_report(s)
        print(f"Trace {i+1} emitted")
    time.sleep(2)                # let the batch flush before exit
