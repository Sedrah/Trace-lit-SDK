"""
Trace-lit API Gateway Proxy.

Zero-code setup for cloud customers — the PM changes two environment variables
in their deployment platform (Vercel, Railway, Render, etc.) and every AI call
is automatically traced. No developer involvement required.

Setup (OpenAI):
    OPENAI_BASE_URL=https://app.trace-lit.com/proxy/openai/v1
    OPENAI_API_KEY=<tracelit-key>||<real-openai-key>

Setup (Anthropic):
    ANTHROPIC_BASE_URL=https://app.trace-lit.com/proxy/anthropic
    ANTHROPIC_API_KEY=<tracelit-key>||<real-anthropic-key>

The proxy:
  1. Splits the combined key → validates Tracelit part, resolves org_id
  2. Forwards request to upstream with the real key
  3. Captures model, tokens, cost, input/output text
  4. Writes a span to ClickHouse (non-blocking background task)
  5. Returns the upstream response unchanged — including streaming
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import Response, StreamingResponse
from starlette.background import BackgroundTask

logger = logging.getLogger("trace_lit.proxy")

router = APIRouter(tags=["proxy"])

_OPENAI_BASE    = "https://api.openai.com"
_ANTHROPIC_BASE = "https://api.anthropic.com"

# Shared async HTTP client — reused across requests for connection pooling
_client: httpx.AsyncClient | None = None

def _http() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0))
    return _client


# ---------------------------------------------------------------------------
# Cost tables (USD per 1k tokens: input, output)
# ---------------------------------------------------------------------------

_OPENAI_COSTS: dict[str, tuple[float, float]] = {
    "gpt-4o-mini":   (0.00015, 0.0006),
    "gpt-4o":        (0.005,   0.015),
    "gpt-4-turbo":   (0.01,    0.03),
    "gpt-4":         (0.03,    0.06),
    "gpt-3.5-turbo": (0.0005,  0.0015),
    "o1-mini":       (0.003,   0.012),
    "o1":            (0.015,   0.060),
}

_ANTHROPIC_COSTS: dict[str, tuple[float, float]] = {
    "claude-3-5-haiku":  (0.0008, 0.004),
    "claude-3-5-sonnet": (0.003,  0.015),
    "claude-3-haiku":    (0.00025,0.00125),
    "claude-3-sonnet":   (0.003,  0.015),
    "claude-3-opus":     (0.015,  0.075),
    "claude-sonnet-4":   (0.003,  0.015),
    "claude-haiku-4":    (0.0008, 0.004),
    "claude-opus-4":     (0.015,  0.075),
}

def _calc_cost(model: str, prompt_tok: int, completion_tok: int, table: dict) -> float:
    for prefix, (in_rate, out_rate) in table.items():
        if model.startswith(prefix):
            return round((prompt_tok * in_rate + completion_tok * out_rate) / 1000, 8)
    return 0.0


# ---------------------------------------------------------------------------
# Key helpers
# ---------------------------------------------------------------------------

def _split_key(combined: str) -> tuple[str, str]:
    """'tracelit-key||upstream-key' → (tracelit_key, upstream_key)."""
    if "||" in combined:
        tl, upstream = combined.split("||", 1)
        return tl.strip(), upstream.strip()
    return combined.strip(), ""

def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()

async def _resolve_org(tl_key: str, request: Request) -> str | None:
    """Resolve org_id from a Tracelit API key (same path as auth.py)."""
    from ..auth import _cache, _lookup_org  # import internals — same process
    key_hash = _sha256(tl_key)
    now = time.monotonic()
    cached = _cache.get(key_hash)
    if cached and cached[1] > now:
        return cached[0]
    return await _lookup_org(key_hash, request)


# ---------------------------------------------------------------------------
# ClickHouse span writer (sync, run in executor)
# ---------------------------------------------------------------------------

_CH_COLUMNS = [
    "org_id", "trace_id", "span_id", "parent_span_id", "timestamp",
    "framework", "agent_name", "action", "status", "duration_ms",
    "input_tokens", "output_tokens", "cost_usd", "model",
    "error_type", "error_msg", "metadata",
    "prompt_name", "prompt_hash", "prompt_version",
    "input_text", "output_text",
]

def _write_span_sync(ch_client: Any, row: list) -> None:
    try:
        ch_client.insert("spans", [row], column_names=_CH_COLUMNS)
    except Exception as exc:
        logger.warning("proxy: span write failed: %s", exc)

async def _write_span(request: Request, row: list) -> None:
    ch = request.app.state.ch_client
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _write_span_sync, ch, row)

def _build_row(
    *,
    org_id: str,
    framework: str,
    agent_name: str,
    action: str,
    model: str,
    status: str,
    duration_ms: float,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    input_text: str | None,
    output_text: str | None,
    error_msg: str = "",
) -> list:
    return [
        org_id,
        str(uuid.uuid4()),   # trace_id — each proxy call is its own trace
        str(uuid.uuid4()),   # span_id
        None,                # parent_span_id
        datetime.now(timezone.utc),
        framework,
        agent_name,
        action,
        status,
        round(duration_ms, 2),
        input_tokens,
        output_tokens,
        cost_usd,
        model,
        "ProxyError" if status == "error" else "",
        error_msg,
        "{}",               # metadata
        None,               # prompt_name
        None,               # prompt_hash
        None,               # prompt_version
        input_text,
        output_text,
    ]


# ---------------------------------------------------------------------------
# Header helpers
# ---------------------------------------------------------------------------

_HOP_BY_HOP = {
    "connection", "keep-alive", "transfer-encoding", "te",
    "trailers", "upgrade", "proxy-authorization", "proxy-authenticate",
}

def _forward_headers(request: Request, upstream_auth: str, auth_header: str) -> dict:
    """Build headers to forward, replacing the auth header with the upstream key."""
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in _HOP_BY_HOP and k.lower() != "host"
    }
    headers[auth_header] = upstream_auth
    return headers


# ---------------------------------------------------------------------------
# OpenAI proxy  —  /proxy/openai/v1/{path}
# ---------------------------------------------------------------------------

@router.api_route(
    "/proxy/openai/v1/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
)
async def proxy_openai(path: str, request: Request) -> Response:
    # Extract combined key from Authorization header
    auth_header = request.headers.get("authorization", "")
    combined = auth_header.removeprefix("Bearer ").removeprefix("bearer ").strip()
    tl_key, openai_key = _split_key(combined)

    org_id = await _resolve_org(tl_key, request)
    if not org_id:
        return Response(
            content=json.dumps({"error": {"message": "Invalid Tracelit API key.", "type": "invalid_request_error"}}),
            status_code=401,
            media_type="application/json",
        )

    body_bytes = await request.body()
    body: dict = {}
    try:
        body = json.loads(body_bytes) if body_bytes else {}
    except json.JSONDecodeError:
        pass

    model   = body.get("model", "unknown")
    stream  = body.get("stream", False)
    agent_name = request.headers.get("x-tracelit-agent", "unknown")

    headers = _forward_headers(request, f"Bearer {openai_key}", "authorization")
    url = f"{_OPENAI_BASE}/v1/{path}"
    t0 = time.monotonic()

    if stream:
        return await _stream_openai(
            request, url, headers, body_bytes, org_id, model, agent_name, t0
        )

    # Non-streaming
    try:
        resp = await _http().request(
            method=request.method,
            url=url,
            headers=headers,
            content=body_bytes,
        )
    except httpx.RequestError as exc:
        return Response(
            content=json.dumps({"error": {"message": str(exc), "type": "api_connection_error"}}),
            status_code=502,
            media_type="application/json",
        )

    duration_ms = (time.monotonic() - t0) * 1000
    _schedule_openai_span(request, resp, org_id, model, agent_name, duration_ms, body)

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=dict(resp.headers),
        media_type=resp.headers.get("content-type"),
    )


def _schedule_openai_span(
    request: Request,
    resp: httpx.Response,
    org_id: str,
    model: str,
    agent_name: str,
    duration_ms: float,
    req_body: dict,
) -> None:
    status = "success" if resp.status_code < 400 else "error"
    input_tokens = output_tokens = 0
    output_text = input_text = None
    error_msg = ""

    try:
        data = resp.json()
        usage = data.get("usage", {})
        input_tokens  = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        model = data.get("model", model)
        if data.get("choices"):
            output_text = data["choices"][0].get("message", {}).get("content")
        messages = req_body.get("messages", [])
        if messages:
            input_text = json.dumps(messages)
        if status == "error":
            error_msg = data.get("error", {}).get("message", "")
    except Exception:
        pass

    cost = _calc_cost(model, input_tokens, output_tokens, _OPENAI_COSTS)
    row = _build_row(
        org_id=org_id, framework="openai-proxy", agent_name=agent_name,
        action="chat.completions", model=model, status=status,
        duration_ms=duration_ms, input_tokens=input_tokens, output_tokens=output_tokens,
        cost_usd=cost, input_text=input_text, output_text=output_text, error_msg=error_msg,
    )
    bg = BackgroundTask(_write_span, request, row)
    # Fire-and-forget — attach to request state so it runs after response
    request.state.proxy_bg = bg
    asyncio.get_event_loop().create_task(_write_span(request, row))


async def _stream_openai(
    request: Request,
    url: str,
    headers: dict,
    body_bytes: bytes,
    org_id: str,
    model: str,
    agent_name: str,
    t0: float,
) -> StreamingResponse:
    req_body: dict = {}
    try:
        req_body = json.loads(body_bytes) if body_bytes else {}
    except json.JSONDecodeError:
        pass

    async def generator() -> AsyncIterator[bytes]:
        accumulated_content = []
        input_tokens = output_tokens = 0
        final_model = model
        status = "success"
        error_msg = ""

        try:
            async with _http().stream(
                "POST", url, headers=headers, content=body_bytes
            ) as resp:
                async for line in resp.aiter_lines():
                    if not line:
                        yield b"\n"
                        continue
                    yield (line + "\n").encode()

                    if line.startswith("data: ") and line != "data: [DONE]":
                        try:
                            chunk = json.loads(line[6:])
                            if chunk.get("model"):
                                final_model = chunk["model"]
                            choices = chunk.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                if delta.get("content"):
                                    accumulated_content.append(delta["content"])
                            usage = chunk.get("usage") or {}
                            if usage:
                                input_tokens  = usage.get("prompt_tokens", input_tokens)
                                output_tokens = usage.get("completion_tokens", output_tokens)
                        except json.JSONDecodeError:
                            pass

        except Exception as exc:
            status = "error"
            error_msg = str(exc)
            logger.warning("proxy: openai stream error: %s", exc)

        duration_ms = (time.monotonic() - t0) * 1000
        messages = req_body.get("messages", [])
        input_text  = json.dumps(messages) if messages else None
        output_text = "".join(accumulated_content) or None
        cost = _calc_cost(final_model, input_tokens, output_tokens, _OPENAI_COSTS)

        row = _build_row(
            org_id=org_id, framework="openai-proxy", agent_name=agent_name,
            action="chat.completions", model=final_model, status=status,
            duration_ms=duration_ms, input_tokens=input_tokens, output_tokens=output_tokens,
            cost_usd=cost, input_text=input_text, output_text=output_text, error_msg=error_msg,
        )
        asyncio.get_event_loop().create_task(_write_span(request, row))

    return StreamingResponse(generator(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Anthropic proxy  —  /proxy/anthropic/v1/{path}
# ---------------------------------------------------------------------------

@router.api_route(
    "/proxy/anthropic/v1/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
)
async def proxy_anthropic(path: str, request: Request) -> Response:
    # Anthropic SDK uses x-api-key header
    combined = request.headers.get("x-api-key", "")
    tl_key, ant_key = _split_key(combined)

    org_id = await _resolve_org(tl_key, request)
    if not org_id:
        return Response(
            content=json.dumps({"type": "error", "error": {"type": "authentication_error", "message": "Invalid Tracelit API key."}}),
            status_code=401,
            media_type="application/json",
        )

    body_bytes = await request.body()
    body: dict = {}
    try:
        body = json.loads(body_bytes) if body_bytes else {}
    except json.JSONDecodeError:
        pass

    model  = body.get("model", "unknown")
    stream = body.get("stream", False)
    agent_name = request.headers.get("x-tracelit-agent", "unknown")

    headers = _forward_headers(request, ant_key, "x-api-key")
    url = f"{_ANTHROPIC_BASE}/v1/{path}"
    t0 = time.monotonic()

    if stream:
        return await _stream_anthropic(
            request, url, headers, body_bytes, org_id, model, agent_name, t0
        )

    try:
        resp = await _http().request(
            method=request.method,
            url=url,
            headers=headers,
            content=body_bytes,
        )
    except httpx.RequestError as exc:
        return Response(
            content=json.dumps({"type": "error", "error": {"type": "api_error", "message": str(exc)}}),
            status_code=502,
            media_type="application/json",
        )

    duration_ms = (time.monotonic() - t0) * 1000
    _schedule_anthropic_span(request, resp, org_id, model, agent_name, duration_ms, body)

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=dict(resp.headers),
        media_type=resp.headers.get("content-type"),
    )


def _schedule_anthropic_span(
    request: Request,
    resp: httpx.Response,
    org_id: str,
    model: str,
    agent_name: str,
    duration_ms: float,
    req_body: dict,
) -> None:
    status = "success" if resp.status_code < 400 else "error"
    input_tokens = output_tokens = 0
    output_text = input_text = None
    error_msg = ""

    try:
        data = resp.json()
        usage = data.get("usage", {})
        input_tokens  = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        model = data.get("model", model)
        content = data.get("content", [])
        if content and content[0].get("type") == "text":
            output_text = content[0]["text"]
        messages = req_body.get("messages", [])
        system   = req_body.get("system", "")
        parts = []
        if system:
            parts.append({"role": "system", "content": system})
        parts.extend(messages)
        input_text = json.dumps(parts) if parts else None
        if status == "error":
            error_msg = data.get("error", {}).get("message", "")
    except Exception:
        pass

    cost = _calc_cost(model, input_tokens, output_tokens, _ANTHROPIC_COSTS)
    row = _build_row(
        org_id=org_id, framework="anthropic-proxy", agent_name=agent_name,
        action="messages", model=model, status=status,
        duration_ms=duration_ms, input_tokens=input_tokens, output_tokens=output_tokens,
        cost_usd=cost, input_text=input_text, output_text=output_text, error_msg=error_msg,
    )
    asyncio.get_event_loop().create_task(_write_span(request, row))


async def _stream_anthropic(
    request: Request,
    url: str,
    headers: dict,
    body_bytes: bytes,
    org_id: str,
    model: str,
    agent_name: str,
    t0: float,
) -> StreamingResponse:
    req_body: dict = {}
    try:
        req_body = json.loads(body_bytes) if body_bytes else {}
    except json.JSONDecodeError:
        pass

    async def generator() -> AsyncIterator[bytes]:
        accumulated_content = []
        input_tokens = output_tokens = 0
        final_model = model
        status = "success"
        error_msg = ""

        try:
            async with _http().stream(
                "POST", url, headers=headers, content=body_bytes
            ) as resp:
                async for line in resp.aiter_lines():
                    if not line:
                        yield b"\n"
                        continue
                    yield (line + "\n").encode()

                    if line.startswith("data: "):
                        try:
                            event = json.loads(line[6:])
                            etype = event.get("type", "")
                            if etype == "content_block_delta":
                                delta = event.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    accumulated_content.append(delta.get("text", ""))
                            elif etype == "message_start":
                                msg = event.get("message", {})
                                final_model = msg.get("model", final_model)
                                usage = msg.get("usage", {})
                                input_tokens = usage.get("input_tokens", input_tokens)
                            elif etype == "message_delta":
                                usage = event.get("usage", {})
                                output_tokens = usage.get("output_tokens", output_tokens)
                        except json.JSONDecodeError:
                            pass

        except Exception as exc:
            status = "error"
            error_msg = str(exc)
            logger.warning("proxy: anthropic stream error: %s", exc)

        duration_ms = (time.monotonic() - t0) * 1000
        messages = req_body.get("messages", [])
        system   = req_body.get("system", "")
        parts = []
        if system:
            parts.append({"role": "system", "content": system})
        parts.extend(messages)
        input_text  = json.dumps(parts) if parts else None
        output_text = "".join(accumulated_content) or None
        cost = _calc_cost(final_model, input_tokens, output_tokens, _ANTHROPIC_COSTS)

        row = _build_row(
            org_id=org_id, framework="anthropic-proxy", agent_name=agent_name,
            action="messages", model=final_model, status=status,
            duration_ms=duration_ms, input_tokens=input_tokens, output_tokens=output_tokens,
            cost_usd=cost, input_text=input_text, output_text=output_text, error_msg=error_msg,
        )
        asyncio.get_event_loop().create_task(_write_span(request, row))

    return StreamingResponse(generator(), media_type="text/event-stream")
