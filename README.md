# Mission Control API

FastAPI backend for the Mission Control earthquake response demo.

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
| GET | `/api/scenario` | Scenario metadata (event list, agents) |
| GET | `/api/state` | Full mission state snapshot |
| GET | `/api/status` | Alias for `/api/state` |
| POST | `/api/simulations/demo/start` | Start the demo |
| WS | `/ws` | Real-time event stream |

### WebSocket Protocol

Connect to `ws://localhost:8000/ws`. The server pushes messages as JSON:

```json
{ "type": "message_type", "data": { ... } }
```

**Message types:**

| Type | Data Shape | When |
|------|-----------|------|
| `mission_started` | `{}` | Demo begins |
| `event` | `MissionEvent` | New earthquake event |
| `agent_response` | `AgentResponse` | Agent finishes analysis |
| `mission_plan` | `MissionPlan` | Commander synthesizes plan |
| `mission_complete` | `{}` | All events processed |
| `error` | `{ message: string }` | Something went wrong |

### Data Models

**MissionEvent:**
```json
{
  "timestamp": "06:32",
  "event_type": "earthquake_detected",
  "severity": "critical",
  "title": "Twin Earthquakes Detected",
  "description": "7.2 and 7.5 magnitude, 38 seconds apart",
  "affected_agents": ["overwatch", "sentinel", "atlas", "pulse", "aegis"]
}
```

**AgentResponse:**
```json
{
  "agent_name": "Intelligence",
  "callsign": "Sentinel",
  "timestamp": "06:32",
  "analysis": "Multiple structural collapses reported in Caracas district...",
  "recommendation": "Deploy urban search and rescue to zone A",
  "confidence": 0.85,
  "priority_change": "increase",
  "resources_needed": ["heavy machinery", "rescue dogs"],
  "risk_score": null
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
    "Activate emergency hospital protocols",
    "Redirect supply convoy via alternate route"
  ],
  "reasoning": "72-hour rescue window requires immediate deployment...",
  "confidence": 0.82
}
```

**MissionStateSnapshot (from GET /api/state):**
```json
{
  "status": "running",
  "scenario": {
    "name": "Venezuela Twin Earthquake Response",
    "description": "...",
    "agents": ["overwatch", "sentinel", "atlas", "pulse", "aegis"],
    "event_count": 10,
    "events": [...]
  },
  "memory": {
    "version": 3,
    "current_risk": "HIGH",
    "event_count": 3,
    "response_count": 15,
    "plan_count": 3,
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
| `overwatch` | Commander — synthesizes mission plans |
| `sentinel` | Intelligence — damage reports, observations |
| `atlas` | Logistics — rescue teams, supply routes |
| `pulse` | Medical — hospitals, triage, shelter health |
| `aegis` | Risk — aftershock probability, stability |

### Severity Levels

`low` | `medium` | `high` | `critical`

### Demo Flow

1. Frontend connects to `ws://localhost:8000/ws`
2. Frontend POSTs to `/api/simulations/demo/start`
3. Server streams 10 events with ~3s gaps
4. Each event triggers 5 parallel agent analyses + 1 commander synthesis
5. Server sends `mission_complete` when done

### CORS

All origins are allowed (`*`). No auth required.

### LLM Configuration

Set in `.env` or environment:

```bash
FIREWORKS_API_KEY=fw_...    # Fireworks AI (default path)
GEMMA_ENDPOINT=...          # AMD MI300X vLLM (overrides Fireworks)
```

When neither is set, agents return deterministic fallback responses.

## Test

```bash
pip install -e ".[dev]"
python -m pytest tests/ -v
```

14 tests: E2E WebSocket demo, architecture contracts, config loading, LLM wiring.
