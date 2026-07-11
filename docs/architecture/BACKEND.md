# Mission Control API Architecture Decision

## Selected backend engine
FastAPI (Python)

## Why this choice
- The source docs already define the backend as FastAPI + WebSockets.
- The product is a real-time orchestration demo, so async WebSocket support is a first-class requirement.
- Python keeps the event/orchestration logic concise and easy to evolve.
- Pydantic gives explicit request/response contracts with strong validation.
- The overview marks Google ADK as optional, so the current runtime uses a thin Python agent layer that can be swapped behind the same interface if ADK is introduced later.

## Alternatives considered
1. **NestJS** — strong structure, but adds TypeScript ceremony that is unnecessary for this small event-driven demo.
2. **Next.js route handlers** — too coupled to the frontend and too easy to turn into a hidden monolith for a WebSocket-heavy backend.
3. **Express** — flexible, but too unstructured for a multi-agent orchestration service.

## Data model summary
The backend is intentionally in-memory for the MVP.

Core models:
- `MissionEvent` — one earthquake response event in the demo timeline
- `AgentResponse` — a deterministic analysis record from one agent
- `MissionPlan` — commander synthesis for the current event
- `MissionMemory` — versioned in-memory history of events, responses, and plans
- `ScenarioDefinition` — metadata for the earthquake demo sequence

No database is used because the overview explicitly excludes persistence from the MVP.

## API contract approach
HTTP:
- `GET /health` — readiness/heartbeat
- `GET /api/scenario` — scenario metadata for the frontend
- `GET /api/state` — current mission status and memory snapshot
- `GET /api/status` — alias for `GET /api/state`
- `POST /api/simulations/demo/start` — starts the demo run

WebSocket:
- `GET /ws` — pushes mission lifecycle messages

WebSocket message types:
- `mission.started`
- `event`
- `agent_response`
- `mission_plan`
- `mission_complete`
- `error`

## LLM wiring approach
- Agents accept an optional OpenAI-compatible LLM client.
- The live client reads `FIREWORKS_API_KEY` for Fireworks by default.
- If `GEMMA_ENDPOINT` is set, the client switches to the AMD MI300X / vLLM path and targets the `google/gemma-4-26b-a4b-it` model.
- Prompt templates live in `src/mission_control_api/prompts/` and are loaded by agent key.
- When no LLM is configured, the backend falls back to deterministic responses so the demo still runs locally and tests stay stable.

## Auth approach
None for MVP.
The overview explicitly says no authentication or user accounts.

## Validation approach
- Pydantic models validate all request/response payloads.
- Route handlers use typed response models or explicit JSON dicts.
- Scenario/event data is constrained with enums and structured models.

## Error handling approach
- Invalid runtime state returns structured HTTP errors.
- WebSocket errors are broadcast as `error` messages when possible.
- Missing optional runtime state fails gracefully instead of crashing the app.

## Testing strategy
- End-to-end API test with `TestClient`
- Health endpoint coverage
- WebSocket stream coverage from mission start to mission completion
- State snapshot verification after the run

The tests are deterministic and do not call external LLMs.

## Deployment assumptions
- Single FastAPI process is enough for the MVP.
- Uvicorn is the runtime.
- No background worker, queue, or database is required yet.
- If the demo later needs real LLM calls, add them behind the agent interface without changing the WebSocket contract.

## Open risks
- In-memory state means a restart loses the current mission.
- The deterministic agents are suitable for e2e validation, but the production demo may later want real LLM-backed reasoning.
- WebSocket clients that connect late will miss earlier streamed events unless a replay buffer is added.
