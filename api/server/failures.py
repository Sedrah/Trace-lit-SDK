"""
Failure classifier — maps raw error_type strings to human-readable categories
and plain-English descriptions for non-developer users.

Rule priority: first match wins.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Classification:
    category: str
    description: str


_RULES: list[tuple[list[str], str, str]] = [
    # (error_type substrings to match, category, description template)
    (
        ["timeout", "timed out", "timedout", "deadline"],
        "LLM Timeout",
        "The language model did not respond in time. This is usually a temporary issue — retrying often works.",
    ),
    (
        ["ratelimit", "rate_limit", "rate limit", "429", "quota"],
        "Rate Limit Exceeded",
        "Too many requests were sent to the AI provider. The agent was throttled.",
    ),
    (
        ["context", "context_length", "maximum context", "token limit", "too long"],
        "Context Length Exceeded",
        "The conversation or input was too long for the model to process. Consider summarising earlier steps.",
    ),
    (
        ["empty", "no output", "none returned", "null output"],
        "Tool Returned Empty",
        "A tool call completed successfully but returned no useful data.",
    ),
    (
        ["tool", "function_call", "function call", "tool_call"],
        "Tool Call Failed",
        "A tool or external function the agent tried to use encountered an error.",
    ),
    (
        ["recursion", "max iterations", "max_iterations", "loop detected", "cycle"],
        "Agent Loop Detected",
        "The agent repeated the same actions multiple times without making progress.",
    ),
    (
        ["authenticationerror", "authentication", "apikey", "api_key", "unauthorized", "403", "401"],
        "Authentication Error",
        "The agent could not authenticate with an AI provider or external service. Check API keys.",
    ),
    (
        ["connection", "connectionerror", "networkerror", "socket", "dns"],
        "Network Error",
        "The agent lost connectivity to an external service.",
    ),
    (
        ["parseerror", "parse error", "json", "invalid response", "decode"],
        "Invalid Response",
        "The model or tool returned data in an unexpected format that the agent could not process.",
    ),
    (
        ["valueerror", "typeerror", "assertionerror", "keyerror", "attributeerror"],
        "Agent Code Error",
        "An unexpected error occurred in the agent's own logic.",
    ),
]


def classify(error_type: Optional[str], error_msg: Optional[str]) -> Classification:
    """
    Return a human-readable classification for a failure span.
    Falls back to 'Unknown Error' if nothing matches.
    """
    haystack = " ".join(
        s.lower() for s in [error_type or "", error_msg or ""] if s
    )

    for keywords, category, description in _RULES:
        if any(kw in haystack for kw in keywords):
            return Classification(category=category, description=description)

    return Classification(
        category="Unknown Error",
        description="An unexpected error occurred. Check the agent logs for more detail.",
    )
