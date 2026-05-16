"use strict";

// test-mock.js — simulates OpenClaw skill hook events without a real session.
//
// Usage:
//   TRACELIT_BROKER=app.trace-lit.com:9093 TRACELIT_API_KEY=sk-demo-abc123 node test-mock.js
//
// On success you should see traces appear at https://app.trace-lit.com
// under agent name "openclaw-test".

process.env.TRACELIT_AGENT_NAME = process.env.TRACELIT_AGENT_NAME || "openclaw-test";

const { activate, deactivate } = require("./src/index.js");

// ── Mock skill object — mimics the OpenClaw skill API ─────────────────────

const handlers = {};

const mockSkill = {
  on(eventName, fn) {
    handlers[eventName] = fn;
    console.log(`  [mock] registered handler for "${eventName}"`);
  },
  log: {
    info:  (msg) => console.log(`  [info]  ${msg}`),
    warn:  (msg) => console.warn(`  [warn]  ${msg}`),
    error: (msg) => console.error(`  [error] ${msg}`),
  },
};

// ── Helper to fire a registered event ─────────────────────────────────────

async function fire(eventName, event) {
  const fn = handlers[eventName];
  if (!fn) {
    console.warn(`  [mock] no handler registered for "${eventName}" — skipping`);
    return;
  }
  console.log(`\n→ firing "${eventName}" (sessionKey: ${event.sessionKey})`);
  await fn(event);
}

// ── Run ────────────────────────────────────────────────────────────────────

async function run() {
  console.log("=== Trace-lit OpenClaw skill mock test ===\n");

  // 1. Activate the skill (connects to Kafka, registers event handlers)
  console.log("Activating skill...");
  await activate(mockSkill);
  console.log();

  const sessionKey = "mock-session-" + Date.now();

  // 2. Simulate command:new (session start)
  await fire("command:new", {
    type: "command",
    action: "new",
    sessionKey,
    timestamp: new Date(),
    context: {
      cfg: { model: "gpt-4o" },
      commandSource: "mock",
      senderId: "tester",
    },
  });

  // 3. Simulate first tool call
  await fire("tool_result_persist", {
    type: "tool",
    action: "result_persist",
    sessionKey,
    timestamp: new Date(),
    context: {
      sessionEntry: {
        tool_name: "bash",
        duration_ms: 450,
        input_tokens: 120,
        output_tokens: 85,
        error: null,
      },
    },
  });

  // 4. Simulate second tool call with an error
  await fire("tool_result_persist", {
    type: "tool",
    action: "result_persist",
    sessionKey,
    timestamp: new Date(),
    context: {
      sessionEntry: {
        tool_name: "web_search",
        duration_ms: 3200,
        input_tokens: 200,
        output_tokens: 0,
        error: "Search provider returned 429 — rate limited",
      },
    },
  });

  // 5. Simulate command:stop (session end)
  await fire("command:stop", {
    type: "command",
    action: "stop",
    sessionKey,
    timestamp: new Date(),
  });

  // 6. Deactivate (flushes Kafka producer)
  console.log("\nDeactivating skill (flushing Kafka)...");
  await deactivate();

  console.log("\n✓ Done — check https://app.trace-lit.com for traces");
}

run().catch((err) => {
  console.error("\n✗ Test failed:", err.message);
  process.exit(1);
});
