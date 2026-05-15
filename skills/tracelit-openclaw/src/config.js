"use strict";

// All configuration comes from environment variables.
// No defaults for credentials — fail loudly if not set.

function getConfig() {
  const broker = process.env.TRACELIT_BROKER;
  const apiKey = process.env.TRACELIT_API_KEY;

  if (!broker) throw new Error("TRACELIT_BROKER is not set");
  if (!apiKey) throw new Error("TRACELIT_API_KEY is not set");

  return {
    broker,
    apiKey,
    agentName: process.env.TRACELIT_AGENT_NAME || "openclaw",
    topic: "trace_lit.spans.raw",
  };
}

module.exports = { getConfig };
