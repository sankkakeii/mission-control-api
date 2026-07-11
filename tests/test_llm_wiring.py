from __future__ import annotations

import asyncio

from mission_control_api.agents import build_agents
from mission_control_api.models import EventSeverity, MissionEvent
from mission_control_api.orchestrator import MissionOrchestrator


class FakeLLMClient:
    def __init__(self):
        self.calls = []

    async def complete_json(
        self, *, schema_name: str, system_prompt: str, user_prompt: str
    ):
        self.calls.append(
            {
                "schema_name": schema_name,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
            }
        )
        if schema_name == "agent_response":
            return {
                "agent_name": "Intelligence",
                "callsign": "Sentinel",
                "timestamp": "06:32",
                "analysis": "LLM analysis for the current event.",
                "recommendation": "LLM recommends prioritizing survivor search.",
                "confidence": 0.93,
                "priority_change": "increase",
                "resources_needed": ["satellite imagery"],
                "risk_score": 0.88,
            }
        return {
            "version": 1,
            "timestamp": "06:32",
            "overall_risk": "HIGH",
            "actions": ["LLM action 1", "LLM action 2"],
            "reasoning": "LLM synthesized the agent responses.",
            "confidence": 0.91,
        }


def test_demo_event_uses_llm_client_when_injected():
    llm = FakeLLMClient()
    orchestrator = MissionOrchestrator(build_agents(llm_client=llm))
    messages: list[dict] = []

    async def broadcast(message: dict) -> None:
        messages.append(message)

    orchestrator.broadcast = broadcast
    event = MissionEvent(
        timestamp="06:32",
        event_type="earthquake_detected",
        severity=EventSeverity.CRITICAL,
        title="Twin earthquakes detected",
        description="7.2 and 7.5 magnitude earthquakes struck 38 seconds apart.",
        affected_agents=["Overwatch", "Sentinel", "Atlas", "Pulse", "Aegis"],
        metadata={"magnitudes": [7.2, 7.5]},
        delay_seconds=0.0,
    )

    plan = asyncio.run(orchestrator.process_event(event))

    assert plan.reasoning == "LLM synthesized the agent responses."
    assert len(llm.calls) == 6
    assert {call["schema_name"] for call in llm.calls} == {
        "agent_response",
        "mission_plan",
    }

    assert messages[0]["type"] == "event"
    assert (
        len([message for message in messages if message["type"] == "agent_response"])
        == 5
    )
    assert messages[-1]["type"] == "mission_plan"
    assert any(
        message["data"]["analysis"] == "LLM analysis for the current event."
        for message in messages
        if message["type"] == "agent_response"
    )
