"""Tests for the failure classifier — pure unit tests, no HTTP needed."""

from __future__ import annotations

from server.failures import classify


def test_timeout_classification() -> None:
    c = classify("TimeoutError", "request timed out after 30s")
    assert c.category == "LLM Timeout"
    assert "temporary" in c.description.lower()


def test_rate_limit_classification() -> None:
    c = classify("RateLimitError", "429 Too Many Requests")
    assert c.category == "Rate Limit Exceeded"


def test_context_length() -> None:
    c = classify("InvalidRequestError", "maximum context length exceeded")
    assert c.category == "Context Length Exceeded"


def test_tool_call_failed() -> None:
    c = classify("ToolException", "tool execution failed")
    assert c.category == "Tool Call Failed"


def test_agent_loop() -> None:
    c = classify("AgentLoopError", "max iterations reached")
    assert c.category == "Agent Loop Detected"


def test_auth_error() -> None:
    c = classify("AuthenticationError", "invalid api key")
    assert c.category == "Authentication Error"


def test_unknown_falls_back() -> None:
    c = classify("WeirdCustomError", "something went very wrong XYZ")
    assert c.category == "Unknown Error"
    assert "logs" in c.description.lower()


def test_none_inputs_return_unknown() -> None:
    c = classify(None, None)
    assert c.category == "Unknown Error"


def test_error_msg_used_when_type_is_generic() -> None:
    # error_type is generic but msg reveals the cause
    c = classify("Exception", "connection refused — socket error")
    assert c.category == "Network Error"
