from __future__ import annotations

from .models import AgentResponse, MissionEvent, MissionMemorySnapshot, MissionPlan


class MissionMemory:
    def __init__(self) -> None:
        self.events: list[MissionEvent] = []
        self.responses: list[list[AgentResponse]] = []
        self.plans: list[MissionPlan] = []
        self.current_risk = "LOW"
        self.version = 0

    def add_event(self, event: MissionEvent, responses: list[AgentResponse], plan: MissionPlan) -> None:
        self.events.append(event)
        self.responses.append(responses)
        self.plans.append(plan)
        self.version += 1
        self.current_risk = plan.overall_risk

    def snapshot(self) -> MissionMemorySnapshot:
        recent_events = [
            {"timestamp": event.timestamp, "description": event.description}
            for event in self.events[-3:]
        ]
        return MissionMemorySnapshot(
            version=self.version,
            current_risk=self.current_risk,
            event_count=len(self.events),
            response_count=sum(len(batch) for batch in self.responses),
            plan_count=len(self.plans),
            recent_events=recent_events,
            latest_plan=self.plans[-1] if self.plans else None,
        )

    def context_lines(self) -> list[str]:
        lines = [f"Current risk level: {self.current_risk}"]
        for event in self.events[-3:]:
            lines.append(f"- {event.timestamp}: {event.description}")
        if self.plans:
            latest = self.plans[-1]
            lines.append(f"Current plan v{latest.version}: {', '.join(latest.actions)}")
        return lines
