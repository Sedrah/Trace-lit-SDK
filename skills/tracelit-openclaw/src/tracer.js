"use strict";

// Tracer — captures OpenClaw session data and emits TraceEvents to Kafka.
//
// Mirrors the Python SDK emitter pattern:
//   - Background producer with delivery callbacks
//   - API key sent in Kafka message headers (never in the payload)
//   - Events are immutable once built
//   - Flush on shutdown to drain the producer queue

const { Kafka } = require("kafkajs");
const { v4: uuidv4 } = require("uuid");

class Tracer {
  constructor(config) {
    this._config = config;
    this._kafka = new Kafka({
      clientId: "tracelit-openclaw",
      brokers: [config.broker],
      // Suppress kafkajs default logger noise in skill context
      logLevel: 1, // ERROR only
    });
    this._producer = this._kafka.producer();
    this._connected = false;
  }

  async connect() {
    await this._producer.connect();
    this._connected = true;
  }

  async disconnect() {
    if (this._connected) {
      await this._producer.disconnect();
      this._connected = false;
    }
  }

  // Build and emit a span for session start.
  async traceSessionStart(session) {
    const event = this._buildEvent({
      traceId: session.traceId,
      spanId: session.spanId,
      parentSpanId: null,
      action: "session_start",
      status: "success",
      durationMs: 0,
      model: session.model || null,
      inputTokens: 0,
      outputTokens: 0,
      errorMessage: null,
    });
    await this._emit(event);
  }

  // Build and emit a span for a single tool call.
  async traceToolCall(session, toolCall) {
    const event = this._buildEvent({
      traceId: session.traceId,
      spanId: uuidv4(),
      parentSpanId: session.spanId,
      action: toolCall.name || "tool_call",
      status: toolCall.error ? "error" : "success",
      durationMs: toolCall.durationMs || 0,
      model: session.model || null,
      inputTokens: toolCall.inputTokens || 0,
      outputTokens: toolCall.outputTokens || 0,
      errorMessage: toolCall.error || null,
    });
    await this._emit(event);
  }

  // Build and emit the final session-end span with totals.
  async traceSessionEnd(session) {
    const event = this._buildEvent({
      traceId: session.traceId,
      spanId: uuidv4(),
      parentSpanId: session.spanId,
      action: "session_end",
      status: session.error ? "error" : "success",
      durationMs: session.durationMs || 0,
      model: session.model || null,
      inputTokens: session.totalInputTokens || 0,
      outputTokens: session.totalOutputTokens || 0,
      errorMessage: session.error || null,
    });
    await this._emit(event);
  }

  _buildEvent({ traceId, spanId, parentSpanId, action, status, durationMs, model, inputTokens, outputTokens, errorMessage }) {
    return {
      // org_id is resolved server-side from the API key — never set in the SDK
      org_id: "default",
      trace_id: traceId,
      span_id: spanId,
      parent_span_id: parentSpanId || null,
      timestamp: new Date().toISOString(),
      framework: "openclaw",
      agent_name: this._config.agentName,
      action,
      status,
      duration_ms: durationMs,
      model: model || null,
      input_tokens: inputTokens,
      output_tokens: outputTokens,
      cost_usd: 0.0, // ingestion pipeline recalculates from tokens + model pricing
      error: errorMessage ? { error_type: "skill_error", message: errorMessage } : null,
      metadata: {},
    };
  }

  async _emit(event) {
    if (!this._connected) return;
    await this._producer.send({
      topic: this._config.topic,
      messages: [
        {
          key: event.trace_id,
          value: JSON.stringify(event),
          headers: {
            // API key in headers — ingestion pipeline resolves to org_id
            "X-Tracelit-Api-Key": this._config.apiKey,
          },
        },
      ],
    });
  }
}

module.exports = { Tracer };
