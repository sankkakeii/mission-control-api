from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware

from .agents import build_agents
from .llm_client import MissionLLMClient, load_llm_client_from_env
from .models import MissionStateSnapshot
from .orchestrator import MissionOrchestrator
from .runtime import MissionRuntime


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


def create_app(
    test_mode: bool = False,
    llm_client: MissionLLMClient | None = None,
) -> FastAPI:
    app = FastAPI(title="Mission Control API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if llm_client is None and not test_mode:
        llm_client = load_llm_client_from_env()

    orchestrator = MissionOrchestrator(build_agents(llm_client=llm_client))
    runtime = MissionRuntime(orchestrator=orchestrator, test_mode=test_mode)
    subscribers: set[asyncio.Queue] = set()

    async def broadcast(message: dict) -> None:
        dead: list[asyncio.Queue] = []
        for queue in subscribers:
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                dead.append(queue)
        for queue in dead:
            subscribers.discard(queue)

    runtime.set_broadcast(broadcast)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "mission-control-api"}

    @app.get("/api/scenario")
    async def get_scenario() -> dict:
        scenario = runtime.scenario
        return {
            "name": scenario.name,
            "description": scenario.description,
            "agents": scenario.agents,
            "event_count": scenario.event_count,
        }

    @app.get("/api/state", response_model=MissionStateSnapshot)
    async def get_state() -> MissionStateSnapshot:
        return MissionStateSnapshot(
            status=runtime.status,
            scenario=runtime.scenario,
            memory=orchestrator.memory.snapshot(),
            agents=orchestrator.agent_statuses(),
        )

    @app.get("/api/status", response_model=MissionStateSnapshot)
    async def get_status() -> MissionStateSnapshot:
        return await get_state()

    @app.post("/api/simulations/demo/start", status_code=status.HTTP_202_ACCEPTED)
    async def start_demo() -> dict[str, str]:
        await runtime.start_demo()
        return {"status": "accepted", "message": "demo started"}

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        queue: asyncio.Queue = asyncio.Queue()
        subscribers.add(queue)
        try:
            while True:
                message = await queue.get()
                await websocket.send_json(message)
                if message.get("type") in {"mission_complete", "error"}:
                    break
        except WebSocketDisconnect:
            pass
        finally:
            subscribers.discard(queue)

    return app


app = create_app()
