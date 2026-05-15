# tracelit-openclaw

OpenClaw skill that sends agent session traces to [Trace-lit](https://app.trace-lit.com) for observability — cost attribution, failure classification, and execution graphs.

## Install

Copy to your OpenClaw skills directory:

```bash
cp -r tracelit-openclaw ~/.openclaw/workspace/skills/
cd ~/.openclaw/workspace/skills/tracelit-openclaw
npm install
```

## Configure

```bash
export TRACELIT_BROKER=app.trace-lit.com:9093
export TRACELIT_API_KEY=your-api-key
```

Use the public demo key `sk-demo-abc123` to try it instantly — traces appear in the shared demo workspace at https://app.trace-lit.com.

## Self-hosted Trace-lit

Point to your own instance:
```bash
export TRACELIT_BROKER=your-server:9093
export TRACELIT_API_KEY=your-key
```

## What gets traced

| Event | Span action | Data captured |
|---|---|---|
| Session starts | `session_start` | model, agent name |
| Tool call | `tool_call` | tool name, duration, tokens, errors |
| Session ends | `session_end` | total tokens, total duration, final status |
