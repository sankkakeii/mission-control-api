from __future__ import annotations

from typing import Any

from .models import AgentResponse, MissionEvent, MissionMemorySnapshot, MissionPlan


class MissionMemory:
    def __init__(self) -> None:
        self.events: list[MissionEvent] = []
        self.responses: list[list[AgentResponse]] = []
        self.plans: list[MissionPlan] = []
        self.current_risk = "LOW"
        self.version = 0
        self.scenario_context: dict[str, Any] | None = None

    def add_event(
        self, event: MissionEvent, responses: list[AgentResponse], plan: MissionPlan
    ) -> None:
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
        if self.scenario_context:
            eq = self.scenario_context.get("earthquake")
            if eq:
                lines.append(
                    f"Earthquake data: M{eq['magnitude']:.1f}, depth {eq['depth_km']:.0f}km, "
                    f"location {eq['place']}, tsunami={'YES' if eq.get('tsunami') else 'no'}, "
                    f"alert={eq.get('alert_level', 'unknown')}"
                )
            infra = self.scenario_context.get("infrastructure")
            if infra:
                lines.append(
                    f"Infrastructure: {infra['hospital_count']} hospitals ({infra.get('total_beds', '?')} beds), "
                    f"{infra['building_count']} mapped structures, "
                    f"{len(infra.get('major_roads', []))} major roads"
                )
                hospitals = infra.get("hospitals", [])
                if hospitals:
                    names = [
                        h["name"]
                        for h in hospitals[:5]
                        if h.get("name") != "Unnamed hospital"
                    ]
                    if names:
                        lines.append(f"Hospitals in range: {', '.join(names)}")
                roads = infra.get("major_roads", [])
                if roads:
                    names = [r["name"] for r in roads[:5] if r.get("name") != "Unnamed"]
                    if names:
                        lines.append(f"Major roads: {', '.join(names)}")
            weather = self.scenario_context.get("weather")
            if weather:
                lines.append(
                    f"Weather: {weather['description']}, {weather['temperature_c']}C, "
                    f"wind {weather['wind_speed_ms']:.0f}m/s, "
                    f"visibility {weather['visibility_m']}m"
                )
                if weather.get("is_night"):
                    lines.append("TIME: Nighttime operations — reduced visibility")
                if weather.get("rain_1h_mm", 0) > 0:
                    lines.append(f"Rain: {weather['rain_1h_mm']:.1f}mm in last hour")
                risk_factors = weather.get("risk_factors", [])
                if risk_factors:
                    lines.append(f"Weather risks: {'; '.join(risk_factors[:3])}")
        return lines
