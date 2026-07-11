# Mission Control API — Frontend Integration Guide

## Base URL

```
https://mission-ctrl.vaporwvre.sbs
```

No auth required. CORS is open (`*`). All responses are JSON.

---

## Quick Start

1. Connect to WebSocket at `wss://mission-ctrl.vaporwvre.sbs/ws`
2. Server auto-starts the demo when WS connects and server is idle
3. Stream events as they come in — each event triggers 5 agent analyses + 1 commander plan
4. Show "MISSION COMPLETE" when you receive `mission_complete`
5. User clicks RESTART → `POST /api/simulations/demo/restart`

---

## REST Endpoints

### `GET /health`
```json
{
  "status": "ok",
  "service": "mission-control-api",
  "live_mode": "true",
  "llm_backend": "openrouter"
}
```

### `GET /api/state`
Returns the full mission state snapshot. Use this to hydrate the UI on page load or reconnect.

```json
{
  "status": "running|idle|completed|error",
  "scenario": { "ScenarioDefinition" },
  "memory": { "MissionMemorySnapshot" },
  "agents": [
    {
      "name": "Intelligence",
      "callsign": "Sentinel",
      "status": "idle|thinking",
      "last_output": "..."
    }
  ]
}
```

### `GET /api/scenario`
Returns scenario metadata without the full event list.

### `POST /api/simulations/demo/start`
Starts the demo. Returns `202 Accepted`. The demo also auto-starts via WebSocket.

### `POST /api/simulations/demo/start?auto=true`
Auto mode — polls USGS every 60s for new earthquakes and chains new scenarios.

### `POST /api/simulations/demo/restart`
Resets all state and starts a fresh demo. **This is what the RESTART button calls.**

---

## WebSocket Protocol

Connect to `wss://mission-ctrl.vaporwvre.sbs/ws`

All messages are JSON objects with a `type` and `data` field:

```json
{ "type": "message_type", "data": { ... } }
```

### Message Types

#### `mission_started`
Sent when a demo begins. Contains the full scenario.

```json
{
  "type": "mission_started",
  "data": {
    "scenario": {
      "name": "Live: M7.5 — 15km NNW of Yaracuy, Venezuela (5 events)",
      "description": "Live USGS data: M7.5 earthquake...",
      "agents": ["Overwatch", "Sentinel", "Atlas", "Pulse", "Aegis"],
      "event_count": 26,
      "events": [ ... ],
      "context": { ... }
    },
    "event_count": 26
  }
}
```

**Frontend action**: Clear all existing events, responses, plans. Set context for maps and panels.

---

#### `event`
A new scenario event. Events come every ~3 seconds.

```json
{
  "type": "event",
  "data": {
    "timestamp": "06:32",
    "event_type": "earthquake_detected",
    "severity": "critical",
    "title": "TWIN EARTHQUAKE: M7.5 — 15km NNW of Yaracuy, Venezuela",
    "description": "Two major earthquakes struck within seconds. M7.5 at 10km depth...",
    "affected_agents": ["Overwatch", "Sentinel", "Atlas", "Pulse", "Aegis"],
    "metadata": {
      "source": "USGS",
      "magnitude": 7.5,
      "depth_km": 10,
      "lat": 10.5,
      "lon": -68.8,
      "tsunami": false,
      "swarm_count": 4
    },
    "delay_seconds": 0.0
  }
}
```

**Frontend action**: Add to event timeline. Set affected agents to "thinking" status. Use `metadata.lat`/`metadata.lon` to position map markers.

---

#### `agent_response`
An AI agent finished analyzing the current event. 5 responses per event.

```json
{
  "type": "agent_response",
  "data": {
    "agent_name": "Intelligence",
    "callsign": "Sentinel",
    "timestamp": "06:32",
    "analysis": "M7.5 earthquake at 10km depth with 4 hospitals and 1,200 beds within 100km radius — mass casualty event likely...",
    "recommendation": "Deploy urban search and rescue to primary collapse zone",
    "confidence": 0.85,
    "priority_change": "increase",
    "resources_needed": ["heavy machinery", "rescue dogs", "satellite uplink"],
    "risk_score": 0.92,
    "citation_score": 0.714,
    "cited_data": ["M7.5", "10km depth", "4 hospitals", "1,200 beds"],
    "missing_data": ["road conditions"]
  }
}
```

**Frontend action**: Add to event feed. Update agent panel (set status back to "idle"). Show citation badge.

---

#### `mission_plan`
Commander synthesizes all 5 agent responses into a unified plan. One plan per event.

```json
{
  "type": "mission_plan",
  "data": {
    "version": 3,
    "timestamp": "06:32",
    "overall_risk": "CRITICAL",
    "actions": [
      "Deploy Urban SAR Team Alpha to collapse zone at coordinates 10.5N, 68.8W",
      "Activate mass casualty protocols at all hospitals in range",
      "Redirect supply convoy via alternate route — primary roads severed"
    ],
    "reasoning": "M7.5 earthquake with 4 hospitals at capacity and tsunami risk requires immediate multi-pronged response...",
    "confidence": 0.82
  }
}
```

`overall_risk` values: `"LOW"` | `"MEDIUM"` | `"HIGH"` | `"CRITICAL"`

**Frontend action**: Update mission plan panel. Update risk indicator in header. Increment plan version.

---

#### `mission_complete`
All events processed. Demo is done.

```json
{
  "type": "mission_complete",
  "data": {
    "status": "completed",
    "plan_version": 26
  }
}
```

**Frontend action**: Show "MISSION COMPLETE" badge. Show RESTART button.

---

#### `error`
Something went wrong.

```json
{
  "type": "error",
  "data": { "message": "Description of what went wrong" }
}
```

---

## Data Models

### Event Types
| event_type | What it means |
|---|---|
| `earthquake_detected` | Initial USGS earthquake detection |
| `commander_assessment` | Overwatch initial situation assessment |
| `tsunami_warning` | Tsunami warning (if applicable) |
| `hospital_capacity` | Hospital overwhelm status |
| `intelligence_sweep` | Sentinel satellite/sensor sweep |
| `building_collapse` | Structural collapses reported |
| `road_blocked` | Supply routes severed |
| `population_risk` | Population at risk estimate |
| `medical_surge` | Medical surge protocol |
| `resource_deployment` | Supply chain activated |
| `comm_status` | Communication infrastructure status |
| `evacuation_order` | Evacuation corridors established |
| `structural_assessment` | Building damage assessment |
| `aftershock` | Seismic swarm / aftershock |
| `weather_alert` | Weather risk factors |
| `logistics_bottleneck` | Supply chain issues |
| `risk_assessment` | Aegis risk matrix update |
| `utilities_disrupted` | Water/sewer/power issues |
| `rescue_window` | 72-hour rescue deadline |
| `power_grid` | Power grid failure |
| `shelter_status` | Emergency shelter status |
| `fire_risk` | Fire/gas leak risk |
| `mutual_aid` | International aid inbound |
| `night_ops` | Night operations |
| `situation_update` | Full situation report |
| `mission_stabilized` | Mission plan locked |
| `system_notice` | System message (rare) |

### Severity Levels
`low` | `medium` | `high` | `critical`

### Agent Callsigns
| Callsign | Agent Name | Role |
|---|---|---|
| `Overwatch` | Commander | Synthesizes mission plans |
| `Sentinel` | Intelligence | Damage reports, observations |
| `Atlas` | Logistics | Rescue teams, supply routes |
| `Pulse` | Medical | Hospitals, triage, shelter health |
| `Aegis` | Risk | Aftershock probability, stability |

---

## Context Object

The `scenario.context` object (available in `mission_started` and `GET /api/state`) contains rich data from real-world sources. Use this for maps, info panels, and data visualizations.

```json
{
  "earthquake": {
    "magnitude": 7.5,
    "depth_km": 10,
    "lat": 10.5,
    "lon": -68.8,
    "place": "15km NNW of Yaracuy, Venezuela",
    "tsunami": false,
    "alert_level": "orange",
    "source": "USGS",
    "usgs_id": "us7000abcd"
  },
  "seismic_swarm": [
    {
      "magnitude": 5.2,
      "place": "South Sandwich Islands region",
      "depth_km": 35,
      "tsunami": false
    }
  ],
  "infrastructure": {
    "hospital_count": 4,
    "total_beds": 1200,
    "building_count": 8500,
    "major_roads": [
      { "name": "Autopista Regional del Centro", "type": "motorway" }
    ],
    "hospitals": [
      { "name": "Hospital Central de Valencia", "beds": 400, "emergency": true }
    ]
  },
  "weather": {
    "temperature_c": 28,
    "humidity": 72,
    "wind_speed_ms": 5,
    "description": "partly cloudy",
    "is_night": false,
    "rain_1h_mm": 0.0,
    "visibility_m": 10000,
    "risk_factors": ["high temperature", "high humidity"]
  }
}
```

Data sources:
- **earthquake** + **seismic_swarm**: USGS GeoJSON feeds (live)
- **infrastructure**: OpenStreetMap Overpass API (hospitals, roads, buildings within 100km)
- **weather**: OpenWeatherMap (current conditions + risk factors)

---

## Event Flow Timing

- Events arrive every **~3 seconds** (configured server-side)
- Each event triggers **5 parallel agent responses** (can take 2-10s each via LLM)
- Each group of 5 responses is followed by **1 commander plan**
- Total: **25-28 events** per scenario
- Full demo duration: **2-5 minutes** depending on LLM response times

---

## Frontend Setup (Next.js)

### next.config.js
```js
module.exports = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "https://mission-ctrl.vaporwvre.sbs/api/:path*",
      },
      {
        source: "/ws",
        destination: "wss://mission-ctrl.vaporwvre.sbs/ws",
      },
    ];
  },
};
```

Or connect directly to the production URL (no proxy needed since CORS is open).

### WebSocket Connection
```ts
const ws = new WebSocket("wss://mission-ctrl.vaporwvre.sbs/ws");

ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  switch (msg.type) {
    case "mission_started":
      // Clear state, set context from msg.data.scenario
      break;
    case "event":
      // Add to timeline, mark agents as "thinking"
      break;
    case "agent_response":
      // Add to feed, mark agent as "idle"
      break;
    case "mission_plan":
      // Update plan panel, risk indicator
      break;
    case "mission_complete":
      // Show completion badge
      break;
    case "error":
      // Show error
      break;
  }
};
```

### RESTART Button
```ts
fetch("https://mission-ctrl.vaporwvre.sbs/api/simulations/demo/restart", {
  method: "POST",
});
```

---

## TypeScript Types

```ts
type EventSeverity = "low" | "medium" | "high" | "critical";

interface MissionEvent {
  timestamp: string;
  event_type: string;
  severity: EventSeverity;
  title: string;
  description: string;
  affected_agents: string[];
  metadata?: Record<string, any>;
  delay_seconds: number;
}

interface AgentResponse {
  agent_name: string;
  callsign: string;
  timestamp: string;
  analysis: string;
  recommendation: string;
  confidence: number;
  priority_change?: string | null;
  resources_needed?: string[] | null;
  risk_score?: number | null;
  citation_score?: number | null;
  cited_data?: string[] | null;
  missing_data?: string[] | null;
}

interface MissionPlan {
  version: number;
  timestamp: string;
  overall_risk: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  actions: string[];
  reasoning: string;
  confidence: number;
}

interface ScenarioDefinition {
  name: string;
  description: string;
  agents: string[];
  event_count: number;
  events: MissionEvent[];
  context?: {
    earthquake?: {
      magnitude: number;
      depth_km: number;
      lat: number;
      lon: number;
      place: string;
      tsunami: boolean;
      alert_level?: string;
      source: string;
      usgs_id: string;
    };
    seismic_swarm?: {
      magnitude: number;
      place: string;
      depth_km: number;
      tsunami: boolean;
    }[];
    infrastructure?: {
      hospital_count: number;
      total_beds: number;
      building_count: number;
      major_roads: { name: string; type: string }[];
      hospitals: { name: string; beds: number; emergency: boolean }[];
    };
    weather?: {
      temperature_c: number;
      humidity: number;
      wind_speed_ms: number;
      description: string;
      is_night: boolean;
      rain_1h_mm: number;
      visibility_m: number;
      risk_factors: string[];
    };
  };
}

interface WSMessage {
  type: "mission_started" | "event" | "agent_response" | "mission_plan" | "mission_complete" | "error";
  data: any;
}
```

---

## Map Data

For geographic visualization:

- **Primary earthquake**: `context.earthquake.lat` + `context.earthquake.lon` — place a pulsing marker here
- **Seismic swarm**: `context.seismic_swarm[]` — no individual coords, but shows magnitude
- **Hospitals**: `context.infrastructure.hospitals[]` — place medical markers
- **Roads**: `context.infrastructure.major_roads[]` — draw route lines
- **Affected area radius**: ~100km from earthquake epicenter

Use Leaflet, Mapbox, or any map library. CartoDB dark tiles work well:
```
https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png
```

---

## Dashboard Layout Suggestion

```
┌──────────────────────────────────────────────────────────────┐
│ HEADER: Connection status | Risk badge | Event counter | RESTART │
├──────────┬───────────────────────────────┬───────────────────┤
│ TIMELINE │ MAP (epicenter + markers)     │ WORLD MAP         │
│ (scroll  │                               │ (highlight zone)  │
│  events) │ MISSION PLAN (actions/reason) │                   │
│          │                               │ CONTEXT PANEL     │
│          │ EVENT FEED (agent responses)  │ (earthquake data, │
│          │                               │  weather, infra)  │
│          │                               │                   │
│          │                               │ AGENT PANEL       │
│          │                               │ (status dots)     │
├──────────┴───────────────────────────────┴───────────────────┤
│ Error toast (bottom center)                                  │
└──────────────────────────────────────────────────────────────┘
```
