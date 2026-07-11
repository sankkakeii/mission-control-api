from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EventSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MissionEvent(BaseModel):
    timestamp: str
    event_type: str
    severity: EventSeverity
    title: str
    description: str
    affected_agents: list[str]
    metadata: dict[str, Any] | None = None
    delay_seconds: float = 0.0


class AgentResponse(BaseModel):
    agent_name: str
    callsign: str
    timestamp: str
    analysis: str
    recommendation: str
    confidence: float = Field(ge=0.0, le=1.0)
    priority_change: str | None = None
    resources_needed: list[str] | None = None
    risk_score: float | None = Field(default=None, ge=0.0, le=1.0)


class MissionPlan(BaseModel):
    version: int
    timestamp: str
    overall_risk: str
    actions: list[str]
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)


class ScenarioDefinition(BaseModel):
    name: str
    description: str
    agents: list[str]
    event_count: int
    events: list[MissionEvent]


class MissionMemorySnapshot(BaseModel):
    version: int
    current_risk: str
    event_count: int
    response_count: int
    plan_count: int
    recent_events: list[dict[str, str]]
    latest_plan: MissionPlan | None = None


class MissionStateSnapshot(BaseModel):
    status: str
    scenario: ScenarioDefinition
    memory: MissionMemorySnapshot
    agents: list[dict[str, Any]]
