from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any

from .agents import BaseAgent, OverwatchAgent
from .mission_memory import MissionMemory
from .models import AgentResponse, MissionEvent, MissionPlan

logger = logging.getLogger(__name__)

AGENT_TIMEOUT_SECONDS = 35


class MissionOrchestrator:
    def __init__(self, agents: list[BaseAgent]):
        self.agents = agents
        self.memory = MissionMemory()
        self.broadcast: Callable[[dict], asyncio.Future] | None = None

    def agent_statuses(self) -> list[dict[str, str | None]]:
        return [agent.status_payload() for agent in self.agents]

    async def process_event(self, event: MissionEvent) -> MissionPlan:
        if self.broadcast is None:
            raise RuntimeError("broadcast callback not configured")

        await self.broadcast({"type": "event", "data": event.model_dump(mode="json")})

        agent_coros = [agent.analyze(event, self.memory) for agent in self.agents]
        raw_results = await asyncio.gather(
            *[
                self._safe_agent(coro, agent)
                for coro, agent in zip(agent_coros, self.agents)
            ],
            return_exceptions=False,
        )
        responses: list[AgentResponse] = [
            r for r in raw_results if isinstance(r, AgentResponse)
        ]

        for response in responses:
            await self.broadcast(
                {"type": "agent_response", "data": response.model_dump(mode="json")}
            )

        commander = next(
            (agent for agent in self.agents if isinstance(agent, OverwatchAgent)), None
        )
        if commander is None:
            raise RuntimeError("Overwatch agent is required")
        plan = await commander.synthesize(responses, self.memory, event)

        self.memory.add_event(event, responses, plan)
        await self.broadcast(
            {"type": "mission_plan", "data": plan.model_dump(mode="json")}
        )
        return plan

    async def _safe_agent(
        self, coro: Coroutine[Any, Any, AgentResponse], agent: BaseAgent
    ) -> AgentResponse | None:
        try:
            return await asyncio.wait_for(coro, timeout=AGENT_TIMEOUT_SECONDS)
        except Exception as exc:
            if "timed out" in str(exc).lower() or isinstance(exc, asyncio.TimeoutError):
                logger.warning(
                    "Agent %s timed out after %ds",
                    agent.callsign,
                    AGENT_TIMEOUT_SECONDS,
                )
            else:
                logger.exception("Agent %s failed", agent.callsign)
            return None
        except Exception:
            logger.exception("Agent %s failed", agent.callsign)
            return None
