from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from .event_engine import EventEngine, _load_cache
from .mission_memory import MissionMemory
from .models import ScenarioDefinition
from .orchestrator import MissionOrchestrator

logger = logging.getLogger(__name__)

AUTO_POLL_INTERVAL = 60


class MissionRuntime:
    def __init__(
        self,
        orchestrator: MissionOrchestrator,
        test_mode: bool = False,
        live_mode: bool = False,
    ):
        self.orchestrator = orchestrator
        self.engine = EventEngine(test_mode=test_mode)
        self.live_mode = live_mode
        self.scenario: ScenarioDefinition = self._load_scenario()
        self.orchestrator.memory.scenario_context = self.scenario.context
        self.status = "idle"
        self._task: asyncio.Task | None = None
        self._auto_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._broadcast: Callable[[dict], Awaitable[None]] | None = None
        self._last_usgs_id: str | None = None

    def _load_scenario(self) -> ScenarioDefinition:
        if self.live_mode:
            try:
                scenario = self.engine.live_scenario()
                if scenario is not None:
                    logger.info("Loaded live USGS scenario: %s", scenario.name)
                    return scenario
                logger.warning("No USGS events found, trying cache")
            except Exception as exc:
                logger.warning("Failed to fetch USGS data (%s), trying cache", exc)

        cached = _load_cache()
        if cached is not None:
            logger.info("Using cached scenario: %s", cached.name)
            return cached

        logger.warning("No cached scenario available, using minimal fallback")
        return self._minimal_fallback()

    @staticmethod
    def _minimal_fallback() -> ScenarioDefinition:
        from .models import EventSeverity, MissionEvent

        return ScenarioDefinition(
            name="No data available",
            description="Unable to fetch earthquake data or load cached scenario. Check network connection.",
            agents=["Overwatch", "Sentinel", "Atlas", "Pulse", "Aegis"],
            event_count=1,
            events=[
                MissionEvent(
                    timestamp="00:00",
                    event_type="system_notice",
                    severity=EventSeverity.LOW,
                    title="Awaiting earthquake data",
                    description="No live USGS data or cached scenarios available. The system will retry when data becomes available.",
                    affected_agents=["Overwatch"],
                    delay_seconds=0.0,
                )
            ],
        )

    def set_broadcast(self, broadcast: Callable[[dict], Awaitable[None]]) -> None:
        self._broadcast = broadcast
        self.orchestrator.broadcast = broadcast

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def auto_running(self) -> bool:
        return self._auto_task is not None and not self._auto_task.done()

    def reset(self) -> None:
        self.orchestrator.memory = MissionMemory()
        self.orchestrator.memory.scenario_context = self.scenario.context
        self.status = "idle"

    async def start_demo(self, auto: bool = False) -> None:
        async with self._lock:
            if self.running:
                return
            if self._broadcast is None:
                raise RuntimeError("broadcast callback not configured")
            self.reset()
            self.status = "running"
            self._task = asyncio.create_task(self._run_demo())
            if auto and not self.auto_running:
                self._auto_task = asyncio.create_task(self._auto_loop())

    def stop_auto(self) -> None:
        if self._auto_task and not self._auto_task.done():
            self._auto_task.cancel()
            self._auto_task = None
            logger.info("Auto mode stopped")

    async def _auto_loop(self) -> None:
        logger.info("Auto mode started — polling USGS every %ds", AUTO_POLL_INTERVAL)
        try:
            while True:
                await asyncio.sleep(AUTO_POLL_INTERVAL)
                if self.running:
                    continue
                try:
                    scenario = self.engine.live_scenario()
                    if scenario is None:
                        logger.info("Auto poll: no new events")
                        continue
                    eq = (
                        scenario.context.get("earthquake", {})
                        if scenario.context
                        else {}
                    )
                    new_id = eq.get("usgs_id")
                    if new_id and new_id == self._last_usgs_id:
                        logger.info("Auto poll: same event %s, skipping", new_id)
                        continue
                    logger.info("Auto poll: new event %s — starting scenario", new_id)
                    self.scenario = scenario
                    self._last_usgs_id = new_id
                    self.reset()
                    self.status = "running"
                    self._task = asyncio.create_task(self._run_demo())
                except asyncio.CancelledError:
                    break
                except Exception as exc:
                    logger.warning("Auto poll failed: %s", exc)
        except asyncio.CancelledError:
            logger.info("Auto mode cancelled")

    async def _run_demo(self) -> None:
        try:
            eq = (
                self.scenario.context.get("earthquake", {})
                if self.scenario.context
                else {}
            )
            self._last_usgs_id = eq.get("usgs_id")
            await self._broadcast(
                {
                    "type": "mission_started",
                    "data": {
                        "scenario": self.scenario.model_dump(mode="json"),
                        "event_count": self.scenario.event_count,
                    },
                }
            )
            for event in self.scenario.events[:25]:
                if event.delay_seconds > 0:
                    await asyncio.sleep(event.delay_seconds)
                await self.orchestrator.process_event(event)
            await self._broadcast(
                {
                    "type": "mission_complete",
                    "data": {
                        "status": "completed",
                        "plan_version": self.orchestrator.memory.version,
                    },
                }
            )
            self.status = "completed"
        except asyncio.CancelledError:
            self.status = "idle"
            raise
        except Exception as exc:
            self.status = "error"
            if self._broadcast is not None:
                await self._broadcast({"type": "error", "data": {"message": str(exc)}})
            raise
