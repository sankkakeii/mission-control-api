# Mission Control API

FastAPI backend for the Mission Control earthquake response demo.

Five AI agents analyze real-time seismic events, debate resource allocation, and produce evolving mission plans — all powered by Gemma 4 on AMD compute.

## Quick Start

```bash
pip install -e ".[dev]"
python -m mission_control_api
```

Server runs at `http://localhost:8000`.

## Integration Guide

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/scenario` | Scenario metadata (event list, agents, context) |
| GET | `/api/state` | Full mission state snapshot |
| GET | `/api/status` | Alias for `/api/state` |
| POST | `/api/simulations/demo/start` | Start the demo (live USGS data) |
| POST | `/api/simulations/demo/start?auto=true` | Auto mode — polls USGS every 60s, chains new scenarios |
| POST | `/api/simulations/demo/restart` | Reset state and re-run the demo |
| WS | `/ws` | Real-time event stream |

### WebSocket Protocol

Connect to `ws://localhost:8000/ws`. The server pushes messages as JSON:

```json
{ "type": "message_type", "data": { ... } }
```

**Message types:**

| Type | Data Shape | When |
|------|-----------|------|
| `mission_started` | `{ scenario: ScenarioDefinition }` | Demo begins |
| `event` | `MissionEvent` | New earthquake event |
| `agent_response` | `AgentResponse` | Agent finishes analysis (includes citation data) |
| `mission_plan` | `MissionPlan` | Commander synthesizes plan |
| `mission_complete` | `{ plan_version: int }` | All events processed |
| `error` | `{ message: string }` | Something went wrong |

### Data Models

**MissionEvent:**
```json
{
  "timestamp": "06:32",
  "event_type": "earthquake_detected",
  "severity": "critical",
  "title": "TWIN EARTHQUAKE: M7.5 — 15km NNW of Yaracuy, Venezuela",
  "description": "Two major earthquakes struck within seconds...",
  "affected_agents": ["Overwatch", "Sentinel", "Atlas", "Pulse", "Aegis"],
  "metadata": { "source": "USGS", "magnitude": 7.5, "lat": 10.5, "lon": -68.8 }
}
```

**AgentResponse:**
```json
{
  "agent_name": "Intelligence",
  "callsign": "Sentinel",
  "timestamp": "06:32",
  "analysis": "M7.5 earthquake at 10km depth with 4 hospitals and 1,200 beds in range — mass casualty likely...",
  "recommendation": "Deploy urban search and rescue to collapse zone",
  "confidence": 0.85,
  "priority_change": "increase",
  "resources_needed": ["heavy machinery", "rescue dogs"],
  "risk_score": 0.92,
  "citation_score": 0.875,
  "cited_data": ["M7.5", "10km depth", "4 hospitals", "1,200 beds"],
  "missing_data": ["road names"]
}
```

**MissionPlan:**
```json
{
  "version": 1,
  "timestamp": "06:32",
  "overall_risk": "CRITICAL",
  "actions": [
    "Deploy Urban SAR Team Alpha to collapse zone",
    "Activate emergency hospital protocols at stated facilities",
    "Redirect supply convoy via alternate route"
  ],
  "reasoning": "M7.5 at 10km depth with 4 hospitals at capacity requires immediate mass casualty response...",
  "confidence": 0.82
}
```

**MissionStateSnapshot (from GET /api/state):**
```json
{
  "status": "running",
  "scenario": {
    "name": "Live: M7.5 — 15km NNW of Yaracuy, Venezuela (4 events)",
    "description": "Live USGS data: M7.5 earthquake...",
    "agents": ["Overwatch", "Sentinel", "Atlas", "Pulse", "Aegis"],
    "event_count": 26,
    "events": [...],
    "context": {
      "earthquake": { "magnitude": 7.5, "depth_km": 10, "lat": 10.5, "lon": -68.8, ... },
      "infrastructure": { "hospital_count": 4, "total_beds": 1200, "building_count": 8500, ... },
      "weather": { "temperature_c": 28, "wind_speed_ms": 5, "description": "partly cloudy", ... },
      "seismic_swarm": [ ... ]
    }
  },
  "memory": {
    "version": 26,
    "current_risk": "CRITICAL",
    "event_count": 26,
    "response_count": 130,
    "plan_count": 26,
    "recent_events": [...],
    "latest_plan": { ... }
  },
  "agents": [
    { "name": "Intelligence", "callsign": "Sentinel", "status": "idle", "last_output": "..." }
  ]
}
```

### Agent Callsigns

| Callsign | Role |
|----------|------|
| `Overwatch` | Commander — synthesizes mission plans |
| `Sentinel` | Intelligence — damage reports, observations |
| `Atlas` | Logistics — rescue teams, supply routes |
| `Pulse` | Medical — hospitals, triage, shelter health |
| `Aegis` | Risk — aftershock probability, stability |

### Severity Levels

`low` | `medium` | `high` | `critical`

### Demo Flow

1. Frontend connects to `ws://localhost:8000/ws`
2. Frontend POSTs to `/api/simulations/demo/start` (or `?auto=true` for continuous mode)
3. Server fetches live USGS earthquake data (with OpenStreetMap infrastructure, OpenWeatherMap weather)
4. Server streams 25+ events with ~3s gaps — each event triggers 5 parallel agent analyses + 1 commander synthesis
5. Every agent response includes citation validation (proving agents reference real data, not hallucinating)
6. Server sends `mission_complete` when done (or continues polling in auto mode)

### Auto Mode

`POST /api/simulations/demo/start?auto=true` enables continuous monitoring:
- Polls USGS every 60 seconds for new earthquakes
- Chains new scenarios as live data arrives
- Max 25 events per scenario to manage LLM costs
- Previous scenario data cached to temp JSON for fallback

### Citation System

Every agent response is validated against the real scenario data:
- **citation_score** (0.0–1.0): % of available data points the agent referenced
- **cited_data**: list of specific data points cited (e.g., "M7.5", "4 hospitals", "28C")
- **missing_data**: data points the agent failed to reference

This proves agents are analyzing real data, not generating generic responses.

### CORS

All origins are allowed (`*`). No auth required.

### LLM Configuration

Set in `.env` or environment:

```bash
LLM_BACKEND=              # auto-detect: fireworks → openrouter → vllm → transformers
FIREWORKS_API_KEY=fw_...  # Fireworks AI serverless (Gemma 4 26B)
OPENROUTER_API_KEY=sk-... # OpenRouter API (Gemma 4 26B, free tier)
GEMMA_ENDPOINT=...        # AMD MI300X vLLM (overrides Fireworks)
HF_TOKEN=hf_...           # HuggingFace token for gated models
LIVE_MODE=true            # Fetch real USGS earthquake data
```

When no LLM key is set, agents return deterministic fallback responses.

## Test

```bash
pip install -e ".[dev]"
python -m pytest tests/ -v
```

17 tests: E2E WebSocket demo, architecture contracts, config loading, LLM wiring.
