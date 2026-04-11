"use strict";

// Trace-lit OpenClaw Skill — entry point.
//
// Hooks into OpenClaw session lifecycle events and sends traces to Trace-lit.
// Activates automatically on session start — no manual instrumentation needed.

const { v4: uuidv4 } = require("uuid");
const { getConfig } = require("./config");
const { Tracer } = require("./tracer");

let tracer = null;

// Called by OpenClaw when the skill is loaded.
async function activate(skill) {
  let config;
  try {
    config = getConfig();
  } catch (err) {
    skill.log.warn(`[tracelit] Skill disabled — ${err.message}`);
    return;
  }

  tracer = new Tracer(config);
  try {
    await tracer.connect();
    skill.log.info("[tracelit] Connected to Trace-lit broker");
  } catch (err) {
    skill.log.warn(`[tracelit] Could not connect to broker — ${err.message}`);
    tracer = null;
    return;
  }

  // ── Session lifecycle hooks ──────────────────────────────────────────────

  skill.on("session:start", async (session) => {
    if (!tracer) return;
    // Attach trace/span IDs to the session so all events share the same trace
    session.traceId = uuidv4();
    session.spanId = uuidv4();
    session.startedAt = Date.now();
    session.totalInputTokens = 0;
    session.totalOutputTokens = 0;

    try {
      await tracer.traceSessionStart(session);
    } catch (err) {
      skill.log.warn(`[tracelit] Failed to emit session_start: ${err.message}`);
    }
  });

  skill.on("tool:call", async (session, toolCall) => {
    if (!tracer || !session.traceId) return;

    // Accumulate token totals on the session
    session.totalInputTokens += toolCall.inputTokens || 0;
    session.totalOutputTokens += toolCall.outputTokens || 0;

    try {
      await tracer.traceToolCall(session, toolCall);
    } catch (err) {
      skill.log.warn(`[tracelit] Failed to emit tool_call: ${err.message}`);
    }
  });

  skill.on("session:end", async (session) => {
    if (!tracer || !session.traceId) return;

    session.durationMs = Date.now() - (session.startedAt || Date.now());

    try {
      await tracer.traceSessionEnd(session);
    } catch (err) {
      skill.log.warn(`[tracelit] Failed to emit session_end: ${err.message}`);
    }
  });
}

// Called by OpenClaw on shutdown — drain the Kafka producer before exit.
async function deactivate() {
  if (tracer) {
    await tracer.disconnect();
    tracer = null;
  }
}

module.exports = { activate, deactivate };
