from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from statistics import mean
from typing import Any

from .llm_client import MissionLLMClient
from .mission_memory import MissionMemory
from .models import AgentResponse, EventSeverity, MissionEvent, MissionPlan
from .prompts import load_prompt

_log = logging.getLogger(__name__)


_SEVERITY_SCORE = {
    EventSeverity.LOW: 0.15,
    EventSeverity.MEDIUM: 0.4,
    EventSeverity.HIGH: 0.7,
    EventSeverity.CRITICAL: 0.95,
}


class BaseAgent(ABC):
    def __init__(
        self, name: str, callsign: str, llm_client: MissionLLMClient | None = None
    ) -> None:
        self.name = name
        self.callsign = callsign
        self.llm_client = llm_client
        self.status = "idle"
        self.last_output: str | None = None

    @abstractmethod
    async def analyze(
        self, event: MissionEvent, memory: MissionMemory
    ) -> AgentResponse:
        raise NotImplementedError

    def status_payload(self) -> dict[str, str | None]:
        return {
            "name": self.name,
            "callsign": self.callsign,
            "status": self.status,
            "last_output": self.last_output,
        }


class OverwatchAgent(BaseAgent):
    def __init__(self, llm_client: MissionLLMClient | None = None) -> None:
        super().__init__(name="Commander", callsign="Overwatch", llm_client=llm_client)

    async def analyze(
        self, event: MissionEvent, memory: MissionMemory
    ) -> AgentResponse:
        self.status = "thinking"
        if self.llm_client is not None:
            try:
                payload = await self.llm_client.complete_json(
                    schema_name="agent_response",
                    system_prompt=_render_prompt(
                        "overwatch", event, memory, responses=""
                    ),
                    user_prompt=_response_instructions(self.name, event),
                )
                response = _build_agent_response(
                    payload, agent_name=self.name, callsign=self.callsign, event=event
                )
            except Exception:
                _log.exception("Overwatch analyze() LLM call failed, falling back")
                response = self._fallback_analyze(event)
        else:
            response = self._fallback_analyze(event)
        self.status = "idle"
        self.last_output = response.analysis
        return response

    def _fallback_analyze(self, event: MissionEvent) -> AgentResponse:
        recommendation = f"Coordinate a unified response for {event.title.lower()} and keep the mission aligned."
        analysis = (
            f"Commander view: the mission is at {event.severity.value.upper()} intensity. "
            f"{event.description}"
        )
        return AgentResponse(
            agent_name=self.name,
            callsign=self.callsign,
            timestamp=event.timestamp,
            analysis=analysis,
            recommendation=recommendation,
            confidence=0.92,
            priority_change="maintain"
            if event.severity == EventSeverity.LOW
            else "increase",
            resources_needed=["command coordination"],
            risk_score=_SEVERITY_SCORE[event.severity],
        )

    async def synthesize(
        self,
        responses: list[AgentResponse],
        memory: MissionMemory,
        event: MissionEvent,
    ) -> MissionPlan:
        self.status = "synthesizing"
        if self.llm_client is not None:
            try:
                payload = await self.llm_client.complete_json(
                    schema_name="mission_plan",
                    system_prompt=_render_synthesis_prompt(responses, memory, event),
                    user_prompt="Synthesize the agent responses into a mission plan JSON object.",
                )
                plan = _build_mission_plan(payload, memory=memory, event=event)
            except Exception:
                _log.exception("Overwatch synthesize() LLM call failed, falling back")
                plan = self._fallback_synthesize(responses, memory, event)
        else:
            plan = self._fallback_synthesize(responses, memory, event)
        self.status = "idle"
        self.last_output = plan.reasoning
        return plan

    def _fallback_synthesize(
        self,
        responses: list[AgentResponse],
        memory: MissionMemory,
        event: MissionEvent,
    ) -> MissionPlan:
        risk_score = max(
            [
                _SEVERITY_SCORE[event.severity],
                *[resp.risk_score or 0.0 for resp in responses],
            ]
        )
        if risk_score >= 0.9:
            overall_risk = "CRITICAL"
        elif risk_score >= 0.65:
            overall_risk = "HIGH"
        elif risk_score >= 0.35:
            overall_risk = "MEDIUM"
        else:
            overall_risk = "LOW"

        actions = [resp.recommendation for resp in responses[:3]]
        actions.append(
            f"Commander directive: preserve rescue tempo for {event.timestamp}."
        )
        return MissionPlan(
            version=memory.version + 1,
            timestamp=event.timestamp,
            overall_risk=overall_risk,
            actions=actions,
            reasoning=f"Synthesized {len(responses)} concurrent agent assessments for {event.title}.",
            confidence=round(mean([resp.confidence for resp in responses] + [0.92]), 2),
        )


class SentinelAgent(BaseAgent):
    def __init__(self, llm_client: MissionLLMClient | None = None) -> None:
        super().__init__(
            name="Intelligence", callsign="Sentinel", llm_client=llm_client
        )

    async def analyze(
        self, event: MissionEvent, memory: MissionMemory
    ) -> AgentResponse:
        self.status = "thinking"
        if self.llm_client is not None:
            try:
                payload = await self.llm_client.complete_json(
                    schema_name="agent_response",
                    system_prompt=_render_prompt("sentinel", event, memory),
                    user_prompt=_response_instructions(self.name, event),
                )
                response = _build_agent_response(
                    payload, agent_name=self.name, callsign=self.callsign, event=event
                )
            except Exception:
                _log.exception("Sentinel analyze() LLM call failed, falling back")
                response = self._fallback_analyze(event, memory)
        else:
            response = self._fallback_analyze(event, memory)
        self.status = "idle"
        self.last_output = response.analysis
        return response

    def _fallback_analyze(
        self, event: MissionEvent, memory: MissionMemory
    ) -> AgentResponse:
        summary = f"Damage analysis: {event.description}"
        recommendation = "Prioritize field reports, structural assessment, and survivor confirmation."
        if event.event_type == "aftershock":
            recommendation = "Re-check collapse zones and suspend entry until structures are reassessed."
        return AgentResponse(
            agent_name=self.name,
            callsign=self.callsign,
            timestamp=event.timestamp,
            analysis=f"{summary} Context: {' | '.join(memory.context_lines())}",
            recommendation=recommendation,
            confidence=0.84,
            priority_change="increase"
            if event.severity != EventSeverity.LOW
            else "maintain",
            resources_needed=["situation reports", "damage assessment"],
            risk_score=_SEVERITY_SCORE[event.severity],
        )


class AtlasAgent(BaseAgent):
    def __init__(self, llm_client: MissionLLMClient | None = None) -> None:
        super().__init__(name="Logistics", callsign="Atlas", llm_client=llm_client)

    async def analyze(
        self, event: MissionEvent, memory: MissionMemory
    ) -> AgentResponse:
        self.status = "thinking"
        if self.llm_client is not None:
            try:
                payload = await self.llm_client.complete_json(
                    schema_name="agent_response",
                    system_prompt=_render_prompt("atlas", event, memory),
                    user_prompt=_response_instructions(self.name, event),
                )
                response = _build_agent_response(
                    payload, agent_name=self.name, callsign=self.callsign, event=event
                )
            except Exception:
                _log.exception("Atlas analyze() LLM call failed, falling back")
                response = self._fallback_analyze(event)
        else:
            response = self._fallback_analyze(event)
        self.status = "idle"
        self.last_output = response.analysis
        return response

    def _fallback_analyze(self, event: MissionEvent) -> AgentResponse:
        recommendation = "Keep supply routes open and stage heavy equipment near the highest-need sector."
        if event.event_type == "road_blocked":
            recommendation = "Reroute convoys, clear debris access, and protect the alternate supply corridor."
        elif event.event_type == "aid_arrival":
            recommendation = "Receive incoming aid, assign staging lanes, and deploy resources by urgency."
        return AgentResponse(
            agent_name=self.name,
            callsign=self.callsign,
            timestamp=event.timestamp,
            analysis=f"Logistics review: {event.title} affects transport, staging, and supply flow.",
            recommendation=recommendation,
            confidence=0.88,
            priority_change="increase"
            if event.event_type in {"road_blocked", "aid_arrival"}
            else "maintain",
            resources_needed=["transport coordination", "heavy machinery"],
            risk_score=_SEVERITY_SCORE[event.severity],
        )


class PulseAgent(BaseAgent):
    def __init__(self, llm_client: MissionLLMClient | None = None) -> None:
        super().__init__(name="Medical", callsign="Pulse", llm_client=llm_client)

    async def analyze(
        self, event: MissionEvent, memory: MissionMemory
    ) -> AgentResponse:
        self.status = "thinking"
        if self.llm_client is not None:
            try:
                payload = await self.llm_client.complete_json(
                    schema_name="agent_response",
                    system_prompt=_render_prompt("pulse", event, memory),
                    user_prompt=_response_instructions(self.name, event),
                )
                response = _build_agent_response(
                    payload, agent_name=self.name, callsign=self.callsign, event=event
                )
            except Exception:
                _log.exception("Pulse analyze() LLM call failed, falling back")
                response = self._fallback_analyze(event)
        else:
            response = self._fallback_analyze(event)
        self.status = "idle"
        self.last_output = response.analysis
        return response

    def _fallback_analyze(self, event: MissionEvent) -> AgentResponse:
        recommendation = "Maintain triage, monitor shelter health, and pre-position medical supplies."
        if event.event_type == "hospital_capacity":
            recommendation = "Escalate triage protocol, divert low-acuity cases, and free emergency beds immediately."
        elif event.event_type == "water_contamination":
            recommendation = "Deploy water treatment and isolate affected shelters to stop secondary illness risk."
        return AgentResponse(
            agent_name=self.name,
            callsign=self.callsign,
            timestamp=event.timestamp,
            analysis=f"Medical triage review: {event.description}",
            recommendation=recommendation,
            confidence=0.9,
            priority_change="increase",
            resources_needed=["triage teams", "medical supply caches"],
            risk_score=_SEVERITY_SCORE[event.severity],
        )


class AegisAgent(BaseAgent):
    def __init__(self, llm_client: MissionLLMClient | None = None) -> None:
        super().__init__(name="Risk", callsign="Aegis", llm_client=llm_client)

    async def analyze(
        self, event: MissionEvent, memory: MissionMemory
    ) -> AgentResponse:
        self.status = "thinking"
        if self.llm_client is not None:
            try:
                payload = await self.llm_client.complete_json(
                    schema_name="agent_response",
                    system_prompt=_render_prompt("aegis", event, memory),
                    user_prompt=_response_instructions(self.name, event),
                )
                response = _build_agent_response(
                    payload, agent_name=self.name, callsign=self.callsign, event=event
                )
            except Exception:
                _log.exception("Aegis analyze() LLM call failed, falling back")
                response = self._fallback_analyze(event)
        else:
            response = self._fallback_analyze(event)
        self.status = "idle"
        self.last_output = response.analysis
        return response

    def _fallback_analyze(self, event: MissionEvent) -> AgentResponse:
        recommendation = "Track structural instability, aftershock probability, and secondary hazard exposure."
        if event.event_type == "aftershock":
            recommendation = "Widen exclusion zones and warn rescue teams about additional collapse risk."
        elif event.event_type == "heavy_rain_forecast":
            recommendation = "Prepare for mudslides, water ingress, and access disruption in unstable districts."
        return AgentResponse(
            agent_name=self.name,
            callsign=self.callsign,
            timestamp=event.timestamp,
            analysis=f"Risk forecast: {event.title} could amplify secondary hazards.",
            recommendation=recommendation,
            confidence=0.86,
            priority_change="increase",
            resources_needed=["hazard modeling", "weather monitoring"],
            risk_score=_SEVERITY_SCORE[event.severity],
        )


def build_agents(llm_client: MissionLLMClient | None = None) -> list[BaseAgent]:
    return [
        OverwatchAgent(llm_client=llm_client),
        SentinelAgent(llm_client=llm_client),
        AtlasAgent(llm_client=llm_client),
        PulseAgent(llm_client=llm_client),
        AegisAgent(llm_client=llm_client),
    ]


def _render_prompt(
    agent_key: str, event: MissionEvent, memory: MissionMemory, responses: str = ""
) -> str:
    template = load_prompt(agent_key)
    return template.format(
        context="\n".join(memory.context_lines()),
        event=json.dumps(event.model_dump(mode="json"), ensure_ascii=False),
        responses=responses,
    )


def _render_synthesis_prompt(
    responses: list[AgentResponse], memory: MissionMemory, event: MissionEvent
) -> str:
    template = load_prompt("overwatch_synthesize")
    return template.format(
        context="\n".join(memory.context_lines()),
        event=json.dumps(event.model_dump(mode="json"), ensure_ascii=False),
        responses=json.dumps(
            [response.model_dump(mode="json") for response in responses],
            ensure_ascii=False,
        ),
    )


def _response_instructions(agent_name: str, event: MissionEvent) -> str:
    return (
        f"Provide the {agent_name} response for event {event.timestamp} ({event.event_type}). "
        "Return JSON only with analysis, recommendation, confidence, priority_change, resources_needed, and risk_score."
    )


def _build_agent_response(
    payload: dict[str, Any],
    *,
    agent_name: str,
    callsign: str,
    event: MissionEvent,
) -> AgentResponse:
    data = {
        **payload,
        "agent_name": payload.get("agent_name", agent_name),
        "callsign": payload.get("callsign", callsign),
        "timestamp": payload.get("timestamp", event.timestamp),
    }
    return AgentResponse.model_validate(data)


def _build_mission_plan(
    payload: dict[str, Any], *, memory: MissionMemory, event: MissionEvent
) -> MissionPlan:
    data = {
        **payload,
        "version": memory.version + 1,
        "timestamp": payload.get("timestamp", event.timestamp),
    }
    return MissionPlan.model_validate(data)
