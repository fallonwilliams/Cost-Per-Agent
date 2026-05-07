# Recursive Systems Platform

 platform for:

1. * recursive-loop analysis** (legacy toolkit).
2. **Recursive AI agent cost rankings**, with browser plugins for Chrome and Firefox.

---

## Features

### Enhancing AI systems with recursive-loop analytics

Generates evidence-ready reports:

- `normalized_claim_events.csv`
- `time_to_ack_report.csv`
- `recursive_loop_report.csv`
- `summary.json`
- `claim_delay_exhibit.md`

### B) AI agent cost ranking API

Ranks recursive AI agents using weighted scoring that favors low cost and penalizes excessive recursion and failure rates.

- Endpoint: `POST /agents/rank`
- Weights must sum to `1.0`:
  - `cost_weight` (default `0.65`)
  - `recursion_weight` (default `0.2`)
  - `reliability_weight` (default `0.15`)

### C) Browser plugin support

Included plugin scaffolds:

- `browser_plugins/chrome` (Manifest V3)
- `browser_plugins/firefox` (Manifest V2)

Both listen for browser-page events in this format:

```js
window.postMessage({
  type: "RECURSIVE_AGENT_RUN",
  run: {
    agent_id: "agent.alpha",
    agent_name: "Alpha Planner",
    provider: "OpenAI",
    model: "gpt-5.3-mini",
    usd_cost: 0.021,
    recursion_depth: 4,
    latency_ms: 1240,
    success: true
  }
}, "*");
```

---

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Run API server

```bash
uvicorn aura_api_server:app --host 0.0.0.0 --port 8000 --reload
```

Useful endpoints:

- `GET /health`
- `POST /analyze`
- `POST /agents/rank`
- `GET /plugins/config`

---

## Example: rank agents by cost

```bash
curl -X POST http://127.0.0.1:8000/agents/rank \
  -H "Content-Type: application/json" \
  -d '{
    "runs": [
      {
        "agent_id": "a1",
        "agent_name": "Planner",
        "provider": "OpenAI",
        "model": "gpt-5.3-mini",
        "usd_cost": 0.012,
        "recursion_depth": 2,
        "latency_ms": 910,
        "success": true
      },
      {
        "agent_id": "a2",
        "agent_name": "Researcher",
        "provider": "Anthropic",
        "model": "claude-sonnet",
        "usd_cost": 0.030,
        "recursion_depth": 5,
        "latency_ms": 1700,
        "success": false
      }
    ]
  }'
```

---

## Legacy claim analyzer CLI

```bash
python claim_loop_analyzer.py --input sample_claim_events.csv --output outputs --ack-hours 168
```

---

## Optional dashboard

Open `webapp/index.html` in a browser while the API is running to view sample ranked output.

