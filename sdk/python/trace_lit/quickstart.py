"""
Entry point for: python -m trace_lit.quickstart

Sends one test trace to the broker and confirms delivery synchronously.
"""
import argparse
import sys
import threading
from datetime import datetime, timezone
from uuid import uuid4

DASHBOARD_URL = "https://app.trace-lit.com"
DEFAULT_BROKER = "app.trace-lit.com:9093"
TOPIC = "trace_lit.spans.raw"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send a test trace to Trace-lit and confirm delivery."
    )
    parser.add_argument("--broker", default=DEFAULT_BROKER, help="Kafka broker (host:port)")
    parser.add_argument("--key", required=True, help="Your Trace-lit API key")
    args = parser.parse_args()

    try:
        from confluent_kafka import Producer
    except ImportError:
        _fail('confluent-kafka not installed. Run: pip install "tracelit-sdk[kafka]"')
        return

    from .models import TraceEvent

    trace_id = uuid4()
    event = TraceEvent(
        trace_id=trace_id,
        span_id=uuid4(),
        timestamp=datetime.now(timezone.utc),
        framework="raw",
        agent_name="quickstart",
        action="test_trace",
        status="success",
        duration_ms=1,
        metadata={"source": "quickstart"},
    )

    delivered = threading.Event()
    errors: list[str] = []

    def on_delivery(err: object, _msg: object) -> None:
        if err:
            errors.append(str(err))
        else:
            delivered.set()

    producer = Producer({"bootstrap.servers": args.broker})
    producer.produce(
        TOPIC,
        key=str(trace_id).encode(),
        value=event.to_kafka_payload(),
        headers=[("X-Tracelit-Api-Key", args.key.encode())],
        on_delivery=on_delivery,
    )
    producer.flush(timeout=15)

    if delivered.is_set():
        print(f"✓ Connected to Trace-lit  ({args.broker})")
        print(f"✓ Test trace sent         (trace_id: {trace_id})")
        print(f"✓ View at {DASHBOARD_URL}")
    else:
        reason = errors[0] if errors else "timeout — broker did not respond within 15s"
        _fail(f"Delivery failed: {reason}\n  Check --broker and --key then try again.")


def _fail(msg: str) -> None:
    print(f"✗ {msg}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
