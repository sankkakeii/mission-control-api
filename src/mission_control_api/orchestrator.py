from __future__ import annotations

import asyncio
from collections.abc import Callable

from .agents import BaseAgent, OverwatchAgent
from .mission_memory import MissionMemory
from .models import AgentResponse, MissionEvent, MissionPlan


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

        agent_tasks = [agent.analyze(event, self.memory) for agent in self.agents]
        responses: list[AgentResponse] = await asyncio.gather(*agent_tasks)

        for response in responses:
            await self.broadcast({"type": "agent_response", "data": response.model_dump(mode="json")})

        commander = next((agent for agent in self.agents if isinstance(agent, OverwatchAgent)), None)
        if commander is None:
            raise RuntimeError("Overwatch agent is required")
        plan = await commander.synthesize(responses, self.memory, event)

        self.memory.add_event(event, responses, plan)
        await self.broadcast({"type": "mission_plan", "data": plan.model_dump(mode="json")})
        return plan
