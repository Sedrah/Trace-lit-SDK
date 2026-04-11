"use strict";

// Trace-lit OpenClaw Skill — entry point.
//
// Hooks into OpenClaw session lifecycle events and sends traces to Trace-lit.
// Activates automatically on session start — no manual instrumentation needed.
//
// Event mapping (confirmed from OpenClaw docs):
//   command:new          → session start
//   command:stop/reset   → session end
//   tool_result_persist  → tool call (synchronous, fires when tool result written)

const { v4: uuidv4 } = require("uuid");
const { getConfig } = require("./config");
const { Tracer } = require("./tracer");

let tracer = null;

// Per-session state keyed by sessionKey — survives across events within a session.
const sessions = new Map();

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

  // ── Session start ─────────────────────────────────────────────────────────
  // command:new fires when the user sends /new

  skill.on("command:new", async (event) => {
    if (!tracer) return;

    const sessionData = {
      traceId: uuidv4(),
      spanId: uuidv4(),
      startedAt: Date.now(),
      totalInputTokens: 0,
      totalOutputTokens: 0,
      model: event.context?.cfg?.model || null,
      agentName: config.agentName,
    };
    sessions.set(event.sessionKey, sessionData);

    try {
      await tracer.traceSessionStart(sessionData);
    } catch (err) {
      skill.log.warn(`[tracelit] Failed to emit session_start: ${err.message}`);
    }
  });

  // ── Tool call ─────────────────────────────────────────────────────────────
  // tool_result_persist fires synchronously when any tool result is written.
  // event.context.sessionEntry contains the tool result data.

  skill.on("tool_result_persist", async (event) => {
    if (!tracer) return;

    const sessionData = sessions.get(event.sessionKey);
    if (!sessionData) return; // session started before skill was active

    const entry = event.context?.sessionEntry || {};
    const toolCall = {
      name: entry.tool_name || entry.name || "tool_call",
      durationMs: entry.duration_ms || 0,
      inputTokens: entry.input_tokens || 0,
      outputTokens: entry.output_tokens || 0,
      error: entry.error || null,
    };

    sessionData.totalInputTokens += toolCall.inputTokens;
    sessionData.totalOutputTokens += toolCall.outputTokens;

    try {
      await tracer.traceToolCall(sessionData, toolCall);
    } catch (err) {
      skill.log.warn(`[tracelit] Failed to emit tool_call: ${err.message}`);
    }
  });

  // ── Session end ───────────────────────────────────────────────────────────
  // command:stop and command:reset both terminate the active session.

  async function handleSessionEnd(event) {
    if (!tracer) return;

    const sessionData = sessions.get(event.sessionKey);
    if (!sessionData) return;

    sessionData.durationMs = Date.now() - sessionData.startedAt;
    sessions.delete(event.sessionKey);

    try {
      await tracer.traceSessionEnd(sessionData);
    } catch (err) {
      skill.log.warn(`[tracelit] Failed to emit session_end: ${err.message}`);
    }
  }

  skill.on("command:stop", handleSessionEnd);
  skill.on("command:reset", handleSessionEnd);
}

// Called by OpenClaw on shutdown — flush any open sessions and disconnect.
async function deactivate() {
  if (tracer) {
    // Flush any sessions that didn't receive a stop/reset event
    for (const [, sessionData] of sessions) {
      sessionData.durationMs = Date.now() - sessionData.startedAt;
      try {
        await tracer.traceSessionEnd(sessionData);
      } catch (_) {}
    }
    sessions.clear();
    await tracer.disconnect();
    tracer = null;
  }
}

module.exports = { activate, deactivate };
