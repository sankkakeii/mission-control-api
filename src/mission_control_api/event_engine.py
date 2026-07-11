from __future__ import annotations

from .models import EventSeverity, MissionEvent, ScenarioDefinition


class EventEngine:
    def __init__(self, test_mode: bool = False):
        self.test_mode = test_mode

    def demo_scenario(self) -> ScenarioDefinition:
        delay = 0.0 if self.test_mode else 0.15
        events = [
            MissionEvent(
                timestamp="06:32",
                event_type="earthquake_detected",
                severity=EventSeverity.CRITICAL,
                title="Twin earthquakes detected",
                description="7.2 and 7.5 magnitude earthquakes struck 38 seconds apart near Caracas and La Guaira.",
                affected_agents=["Overwatch", "Sentinel", "Atlas", "Pulse", "Aegis"],
                metadata={"magnitudes": [7.2, 7.5]},
                delay_seconds=delay,
            ),
            MissionEvent(
                timestamp="06:35",
                event_type="building_collapse",
                severity=EventSeverity.CRITICAL,
                title="Building collapses reported",
                description="Collapsed structures and trapped civilians are reported across the impact zone.",
                affected_agents=["Sentinel", "Atlas", "Pulse"],
                delay_seconds=delay,
            ),
            MissionEvent(
                timestamp="06:38",
                event_type="hospital_capacity",
                severity=EventSeverity.HIGH,
                title="Hospital capacity critical",
                description="Emergency departments are at capacity and triage teams are overwhelmed.",
                affected_agents=["Pulse", "Overwatch"],
                delay_seconds=delay,
            ),
            MissionEvent(
                timestamp="06:41",
                event_type="aftershock",
                severity=EventSeverity.HIGH,
                title="Aftershock detected",
                description="A magnitude 5.8 aftershock increases collapse risk in partially damaged zones.",
                affected_agents=["Aegis", "Sentinel", "Atlas"],
                delay_seconds=delay,
            ),
            MissionEvent(
                timestamp="06:44",
                event_type="road_blocked",
                severity=EventSeverity.MEDIUM,
                title="Road to La Guaira blocked",
                description="Primary supply routes are blocked by debris and utility damage.",
                affected_agents=["Atlas"],
                delay_seconds=delay,
            ),
            MissionEvent(
                timestamp="06:47",
                event_type="aid_arrival",
                severity=EventSeverity.MEDIUM,
                title="International aid arrives",
                description="International teams and supplies begin arriving at the staging area.",
                affected_agents=["Atlas", "Overwatch"],
                delay_seconds=delay,
            ),
            MissionEvent(
                timestamp="06:50",
                event_type="water_contamination",
                severity=EventSeverity.HIGH,
                title="Water contamination in shelters",
                description="Shelter water supplies show contamination and sanitation risk is rising.",
                affected_agents=["Pulse", "Aegis"],
                delay_seconds=delay,
            ),
            MissionEvent(
                timestamp="06:53",
                event_type="rescue_window",
                severity=EventSeverity.CRITICAL,
                title="72-hour rescue window closing",
                description="The high-probability rescue window is closing and priorities must sharpen.",
                affected_agents=["Overwatch", "Sentinel", "Atlas", "Pulse", "Aegis"],
                delay_seconds=delay,
            ),
            MissionEvent(
                timestamp="06:56",
                event_type="heavy_rain_forecast",
                severity=EventSeverity.HIGH,
                title="Heavy rain forecast",
                description="Forecast heavy rain raises mudslide and access risk in unstable districts.",
                affected_agents=["Aegis", "Atlas", "Pulse"],
                delay_seconds=delay,
            ),
            MissionEvent(
                timestamp="06:59",
                event_type="mission_stabilized",
                severity=EventSeverity.LOW,
                title="Mission stabilizes",
                description="Rescue operations transition toward stabilization and recovery planning.",
                affected_agents=["Overwatch", "Sentinel", "Atlas", "Pulse", "Aegis"],
                delay_seconds=delay,
            ),
        ]
        return ScenarioDefinition(
            name="Earthquake Response",
            description="A real-time earthquake response command center with five coordinated agents.",
            agents=["Overwatch", "Sentinel", "Atlas", "Pulse", "Aegis"],
            event_count=len(events),
            events=events,
        )
