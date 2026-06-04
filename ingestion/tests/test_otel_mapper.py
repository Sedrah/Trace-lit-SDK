"""Tests for OTel → TraceEvent mapping (no infra needed)."""
import base64

from pipeline.otel.mapper import map_otlp_json


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


TRACE_ID_BYTES = bytes.fromhex("0af7651916cd43dd8448eb211c80319c")
SPAN_ID_BYTES  = bytes.fromhex("b7ad6b7169203331")
PARENT_ID_BYTES = bytes.fromhex("00f067aa0ba902b7")


def _minimal_payload(*, scope_name: str = "", span_name: str = "ChatOpenAI", attrs=None) -> dict:
    return {
        "resourceSpans": [{
            "resource": {"attributes": [
                {"key": "service.name", "value": {"stringValue": "grid-agent"}},
            ]},
            "scopeSpans": [{
                "scope": {"name": scope_name},
                "spans": [{
                    "traceId": _b64(TRACE_ID_BYTES),
                    "spanId":  _b64(SPAN_ID_BYTES),
                    "parentSpanId": _b64(PARENT_ID_BYTES),
                    "name": span_name,
                    "startTimeUnixNano": "1700000000000000000",
                    "endTimeUnixNano":   "1700000001500000000",
                    "status": {"code": 1},
                    "attributes": attrs or [],
                    "events": [],
                }],
            }],
        }]
    }


def test_basic_mapping():
    events = map_otlp_json(_minimal_payload(), org_id="acme")
    assert len(events) == 1
    e = events[0]
    assert e.org_id == "acme"
    assert e.agent_name == "grid-agent"
    assert e.action == "ChatOpenAI"
    assert e.status == "success"
    assert e.duration_ms == 1500
    assert e.framework == "raw"


def test_langchain_scope_detected():
    events = map_otlp_json(
        _minimal_payload(scope_name="openinference.instrumentation.langchain"),
        org_id="acme",
    )
    assert events[0].framework == "langchain"


def test_langgraph_scope_detected():
    events = map_otlp_json(
        _minimal_payload(scope_name="openinference.instrumentation.langgraph"),
        org_id="acme",
    )
    assert events[0].framework == "langgraph"


def test_token_attrs_gen_ai():
    attrs = [
        {"key": "gen_ai.request.model",       "value": {"stringValue": "gpt-4o"}},
        {"key": "gen_ai.usage.input_tokens",   "value": {"intValue": "120"}},
        {"key": "gen_ai.usage.output_tokens",  "value": {"intValue": "45"}},
    ]
    e = map_otlp_json(_minimal_payload(attrs=attrs), org_id="acme")[0]
    assert e.model == "gpt-4o"
    assert e.input_tokens == 120
    assert e.output_tokens == 45


def test_token_attrs_openinference():
    attrs = [
        {"key": "llm.model_name",             "value": {"stringValue": "llama3"}},
        {"key": "llm.token_count.prompt",      "value": {"intValue": "80"}},
        {"key": "llm.token_count.completion",  "value": {"intValue": "30"}},
    ]
    e = map_otlp_json(_minimal_payload(attrs=attrs), org_id="acme")[0]
    assert e.model == "llama3"
    assert e.input_tokens == 80
    assert e.output_tokens == 30


def test_exception_event_sets_error_status():
    payload = _minimal_payload()
    payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["events"] = [{
        "name": "exception",
        "attributes": [
            {"key": "exception.type",    "value": {"stringValue": "ValueError"}},
            {"key": "exception.message", "value": {"stringValue": "bad input"}},
        ],
    }]
    e = map_otlp_json(payload, org_id="acme")[0]
    assert e.status == "error"
    assert e.error is not None
    assert e.error.error_type == "ValueError"
    assert e.error.message == "bad input"


def test_status_code_error():
    payload = _minimal_payload()
    payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["status"] = {"code": 2}
    e = map_otlp_json(payload, org_id="acme")[0]
    assert e.status == "error"


def test_hex_trace_id():
    """Python OTel SDK ≥1.20 sends hex IDs instead of base64."""
    payload = _minimal_payload()
    payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["traceId"] = TRACE_ID_BYTES.hex()
    payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["spanId"]  = SPAN_ID_BYTES.hex()
    e = map_otlp_json(payload, org_id="acme")[0]
    assert str(e.trace_id).replace("-", "") == TRACE_ID_BYTES.hex()


def test_parent_id_set():
    e = map_otlp_json(_minimal_payload(), org_id="acme")[0]
    assert e.parent_span_id is not None


def test_empty_payload():
    assert map_otlp_json({}, org_id="acme") == []


def test_malformed_span_skipped():
    payload = {
        "resourceSpans": [{
            "resource": {"attributes": []},
            "scopeSpans": [{
                "scope": {},
                "spans": [{"name": "broken"}],  # missing traceId/spanId
            }],
        }]
    }
    # Should not raise; malformed span is silently skipped
    events = map_otlp_json(payload, org_id="acme")
    assert events == []
