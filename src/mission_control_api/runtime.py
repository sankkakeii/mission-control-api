from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from .event_engine import EventEngine
from .models import ScenarioDefinition
from .orchestrator import MissionOrchestrator


class MissionRuntime:
    def __init__(self, orchestrator: MissionOrchestrator, test_mode: bool = False):
        self.orchestrator = orchestrator
        self.engine = EventEngine(test_mode=test_mode)
        self.scenario: ScenarioDefinition = self.engine.demo_scenario()
        self.status = "idle"
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._broadcast: Callable[[dict], Awaitable[None]] | None = None

    def set_broadcast(self, broadcast: Callable[[dict], Awaitable[None]]) -> None:
        self._broadcast = broadcast
        self.orchestrator.broadcast = broadcast

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start_demo(self) -> None:
        async with self._lock:
            if self.running:
                return
            if self._broadcast is None:
                raise RuntimeError("broadcast callback not configured")
            self.status = "running"
            self._task = asyncio.create_task(self._run_demo())

    async def _run_demo(self) -> None:
        try:
            await self._broadcast({
                "type": "mission.started",
                "data": {
                    "scenario": self.scenario.model_dump(mode="json"),
                    "event_count": self.scenario.event_count,
                },
            })
            for event in self.scenario.events:
                if event.delay_seconds > 0:
                    await asyncio.sleep(event.delay_seconds)
                await self.orchestrator.process_event(event)
            await self._broadcast({
                "type": "mission_complete",
                "data": {
                    "status": "completed",
                    "plan_version": self.orchestrator.memory.version,
                },
            })
            self.status = "completed"
        except Exception as exc:  # pragma: no cover - surfaces through error message
            self.status = "error"
            if self._broadcast is not None:
                await self._broadcast({"type": "error", "data": {"message": str(exc)}})
            raise
