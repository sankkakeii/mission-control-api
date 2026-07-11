from __future__ import annotations

import json
import logging
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .models import EventSeverity, MissionEvent, ScenarioDefinition
from .usgs_client import USGSEarthquake, fetch_earthquakes

logger = logging.getLogger(__name__)

DEMO_DELAY = 3.0
_CACHE_DIR = Path(tempfile.gettempdir()) / "mission_control"
_CACHE_FILE = _CACHE_DIR / "last_scenario.json"


def _severity_for_magnitude(mag: float) -> EventSeverity:
    if mag >= 6.0:
        return EventSeverity.CRITICAL
    if mag >= 5.0:
        return EventSeverity.HIGH
    if mag >= 4.0:
        return EventSeverity.MEDIUM
    return EventSeverity.LOW


def _format_ts(ms: int) -> str:
    dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    return dt.strftime("%H:%M")


def _stagger_ts(ms: int, offset_minutes: int) -> str:
    dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    dt = dt + timedelta(minutes=offset_minutes)
    return dt.strftime("%H:%M")


def _save_cache(scenario: ScenarioDefinition) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(
            json.dumps(scenario.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("Cached scenario to %s", _CACHE_FILE)
    except Exception as exc:
        logger.warning("Failed to cache scenario: %s", exc)


def _load_cache() -> ScenarioDefinition | None:
    if not _CACHE_FILE.exists():
        return None
    try:
        data = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        scenario = ScenarioDefinition.model_validate(data)
        logger.info("Loaded cached scenario: %s", scenario.name)
        return scenario
    except Exception as exc:
        logger.warning("Failed to load cache: %s", exc)
        return None


class EventEngine:
    def __init__(self, test_mode: bool = False):
        self.test_mode = test_mode

    def live_scenario(
        self, feed: str = "significant_month"
    ) -> ScenarioDefinition | None:
        quakes = fetch_earthquakes(feed=feed, limit=5)
        if not quakes:
            logger.warning("No earthquakes found in USGS feed %r", feed)
            return None

        primary = max(quakes, key=lambda q: q.magnitude)
        secondaries = [q for q in quakes if q.usgs_id != primary.usgs_id][:4]

        lat, lon = primary.latitude, primary.longitude
        mag = primary.magnitude
        place = primary.place
        base_ms = primary.timestamp_ms
        ts0 = _format_ts(base_ms)
        severity = _severity_for_magnitude(mag)

        infrastructure = None
        weather = None
        context: dict[str, Any] = {
            "earthquake": {
                "magnitude": mag,
                "depth_km": primary.depth_km,
                "lat": lat,
                "lon": lon,
                "place": place,
                "tsunami": primary.tsunami,
                "alert_level": primary.alert_level,
                "source": "USGS",
                "usgs_id": primary.usgs_id,
            },
            "seismic_swarm": [
                {
                    "magnitude": q.magnitude,
                    "place": q.place,
                    "depth_km": q.depth_km,
                    "tsunami": q.tsunami,
                }
                for q in secondaries
            ],
        }

        try:
            from .infrastructure_client import fetch_infrastructure

            infrastructure = fetch_infrastructure(lat, lon, radius_km=100.0)
            context["infrastructure"] = {
                "hospital_count": infrastructure.hospital_count,
                "total_beds": infrastructure.total_beds,
                "building_count": infrastructure.building_count,
                "major_roads": [
                    {"name": r.name, "type": r.highway_type}
                    for r in infrastructure.major_roads[:10]
                ],
                "hospitals": [
                    {"name": h.name, "beds": h.beds, "emergency": h.emergency}
                    for h in infrastructure.hospitals[:10]
                ],
            }
            logger.info(
                "Fetched infrastructure: %d hospitals, %d buildings, %d roads",
                infrastructure.hospital_count,
                infrastructure.building_count,
                len(infrastructure.major_roads),
            )
        except Exception as exc:
            logger.warning("Failed to fetch infrastructure data: %s", exc)

        try:
            from .weather_client import fetch_weather

            weather = fetch_weather(lat, lon)
            if weather:
                context["weather"] = {
                    "temperature_c": weather.temperature_c,
                    "humidity": weather.humidity_percent,
                    "wind_speed_ms": weather.wind_speed_ms,
                    "description": weather.description,
                    "is_night": weather.is_night,
                    "rain_1h_mm": weather.rain_1h_mm,
                    "visibility_m": weather.visibility_m,
                    "risk_factors": weather.risk_factors,
                }
                logger.info(
                    "Fetched weather: %s, %sC",
                    weather.description,
                    weather.temperature_c,
                )
        except Exception as exc:
            logger.warning("Failed to fetch weather data: %s", exc)

        events: list[MissionEvent] = []
        delay = 0.0
        minute = 0

        all_agents = ["Overwatch", "Sentinel", "Atlas", "Pulse", "Aegis"]

        if mag >= 7.0:
            title = f"TWIN EARTHQUAKE: M{mag:.1f} — {place}"
            desc = (
                f"Two major earthquakes struck {place} within seconds. "
                f"M{mag:.1f} at {primary.depth_km:.0f}km depth. "
                f"USGS PAGER alert: {primary.alert_level or 'red'}. "
                f"Mass casualties expected. All response units activated."
            )
        elif mag >= 6.0:
            title = f"CRITICAL: M{mag:.1f} earthquake — {place}"
            desc = (
                f"Major earthquake M{mag:.1f} at {primary.depth_km:.0f}km depth near {place}. "
                f"USGS alert level: {primary.alert_level or 'orange'}. "
                f"Significant damage likely. Emergency response mobilized."
            )
        elif mag >= 5.0:
            title = f"M{mag:.1f} earthquake — {place}"
            desc = (
                f"M{mag:.1f} earthquake near {place}, depth {primary.depth_km:.0f}km. "
                f"USGS alert: {primary.alert_level or 'yellow'}. "
                f"Moderate to strong shaking reported. Assessing damage."
            )
        else:
            title = f"M{mag:.1f} earthquake — {place}"
            desc = (
                f"M{mag:.1f} earthquake near {place}, depth {primary.depth_km:.0f}km. "
                f"Monitoring for structural impact."
            )

        swarm_summary = ""
        if secondaries:
            swarm_summary = ", ".join(
                f"M{q.magnitude:.1f} at {q.place}" for q in secondaries
            )
            desc += f" Seismic swarm detected: {len(secondaries)} additional events ({swarm_summary})."

        # 1. Initial detection
        events.append(
            MissionEvent(
                timestamp=ts0,
                event_type="earthquake_detected",
                severity=severity,
                title=title,
                description=desc,
                affected_agents=all_agents,
                metadata={
                    "source": "USGS",
                    "magnitude": mag,
                    "depth_km": primary.depth_km,
                    "lat": lat,
                    "lon": lon,
                    "tsunami": primary.tsunami,
                    "swarm_count": len(secondaries),
                },
                delay_seconds=delay,
            )
        )
        minute += 2

        # 2. Overwatch initial assessment
        events.append(
            MissionEvent(
                timestamp=_stagger_ts(base_ms, minute),
                event_type="commander_assessment",
                severity=EventSeverity.HIGH,
                title="Overwatch: Situation assessment — initiating response protocol",
                description=(
                    f"Overwatch confirms M{mag:.1f} event at {place}. "
                    f"Estimated affected population within 50km radius. "
                    f"Activating five-agent coordination protocol. Standing by for intelligence updates."
                ),
                affected_agents=["Overwatch"],
                delay_seconds=DEMO_DELAY,
            )
        )
        minute += 2

        # 3. Tsunami warning if applicable
        if primary.tsunami:
            events.append(
                MissionEvent(
                    timestamp=_stagger_ts(base_ms, minute),
                    event_type="tsunami_warning",
                    severity=EventSeverity.CRITICAL,
                    title="TSUNAMI WARNING — evacuate coast",
                    description=(
                        f"Tsunami warning issued for coastline near {place}. "
                        f"All coastal zones within 500km must evacuate immediately."
                    ),
                    affected_agents=all_agents,
                    delay_seconds=DEMO_DELAY,
                )
            )
            minute += 3

        # 4. Hospital capacity
        hospital_bed_info = ""
        if infrastructure and infrastructure.hospital_count > 0:
            hospital_names = [
                h.name
                for h in infrastructure.hospitals[:3]
                if h.name != "Unnamed hospital"
            ]
            hospital_list = (
                ", ".join(hospital_names)
                if hospital_names
                else f"{infrastructure.hospital_count} facilities"
            )
            hospital_bed_info = (
                f" Total bed capacity: ~{infrastructure.total_beds}."
                if infrastructure.total_beds
                else ""
            )
            events.append(
                MissionEvent(
                    timestamp=_stagger_ts(base_ms, minute),
                    event_type="hospital_capacity",
                    severity=EventSeverity.CRITICAL
                    if mag >= 7.0
                    else EventSeverity.HIGH,
                    title="Hospitals overwhelmed — mass casualty declared",
                    description=(
                        f"Hospitals in range: {hospital_list}.{hospital_bed_info} "
                        f"Emergency departments at surge capacity. "
                        f"Field hospitals being established. Mass casualty protocol activated."
                    ),
                    affected_agents=["Pulse", "Overwatch"],
                    delay_seconds=DEMO_DELAY,
                )
            )
        else:
            events.append(
                MissionEvent(
                    timestamp=_stagger_ts(base_ms, minute),
                    event_type="hospital_capacity",
                    severity=EventSeverity.CRITICAL
                    if mag >= 7.0
                    else EventSeverity.HIGH,
                    title="Hospitals overwhelmed — mass casualty declared",
                    description=(
                        f"Emergency departments near {place} are at surge capacity. "
                        f"Mass casualty protocol activated. Triage teams overwhelmed."
                    ),
                    affected_agents=["Pulse", "Overwatch"],
                    delay_seconds=DEMO_DELAY,
                )
            )
        minute += 3

        # 5. Sentinel intelligence sweep
        events.append(
            MissionEvent(
                timestamp=_stagger_ts(base_ms, minute),
                event_type="intelligence_sweep",
                severity=EventSeverity.MEDIUM,
                title="Sentinel: Seismic intelligence sweep complete",
                description=(
                    f"Satellite and sensor sweep of {place} impact zone complete. "
                    f"Detected structural damage signatures across {int(20 + mag * 5)}km radius. "
                    f"Population density estimates suggest {int(50000 + mag * 15000)} people in affected zone. "
                    f"Relaying classified damage assessment to all agents."
                ),
                affected_agents=["Sentinel", "Overwatch"],
                delay_seconds=DEMO_DELAY,
            )
        )
        minute += 2

        # 6. Building collapse
        building_note = ""
        if infrastructure and infrastructure.building_count > 0:
            building_note = f" Area contains ~{infrastructure.building_count} mapped structures at risk."
        events.append(
            MissionEvent(
                timestamp=_stagger_ts(base_ms, minute),
                event_type="building_collapse",
                severity=EventSeverity.CRITICAL if mag >= 7.0 else EventSeverity.HIGH,
                title="Structures collapsing — search and rescue NOW",
                description=(
                    f"Multiple building collapses reported across the {place} impact zone.{building_note} "
                    f"Trapped civilians detected. Deploying urban search and rescue teams."
                ),
                affected_agents=["Sentinel", "Atlas", "Pulse"],
                delay_seconds=DEMO_DELAY,
            )
        )
        minute += 3

        # 7. Road damage
        if infrastructure and infrastructure.major_roads:
            road_names = [
                r.name for r in infrastructure.major_roads[:4] if r.name != "Unnamed"
            ]
            road_list = (
                ", ".join(road_names)
                if road_names
                else f"{len(infrastructure.major_roads)} major routes"
            )
        else:
            road_list = "primary arterial routes"
        events.append(
            MissionEvent(
                timestamp=_stagger_ts(base_ms, minute),
                event_type="road_blocked",
                severity=EventSeverity.HIGH,
                title="Supply routes severed — alternate paths needed",
                description=(
                    f"Major roads affected: {road_list}. "
                    f"Critical supply lines to {place} are cut. "
                    f"Atlas deploying airlift and alternate ground routes."
                ),
                affected_agents=["Atlas", "Sentinel"],
                delay_seconds=DEMO_DELAY,
            )
        )
        minute += 3

        # 8. Population at risk
        pop_est = int(50000 + mag * 15000)
        events.append(
            MissionEvent(
                timestamp=_stagger_ts(base_ms, minute),
                event_type="population_risk",
                severity=EventSeverity.CRITICAL if mag >= 7.0 else EventSeverity.HIGH,
                title=f"Population at risk: ~{pop_est:,} in impact zone",
                description=(
                    f"Sentinel estimates {pop_est:,} people within the high-risk zone near {place}. "
                    f"Evacuation corridors identified. Vulnerable populations (elderly, hospitals, schools) "
                    f"flagged for priority extraction. Medical surge capacity being calculated."
                ),
                affected_agents=["Sentinel", "Pulse", "Atlas"],
                delay_seconds=DEMO_DELAY,
            )
        )
        minute += 3

        # 9. Medical surge
        events.append(
            MissionEvent(
                timestamp=_stagger_ts(base_ms, minute),
                event_type="medical_surge",
                severity=EventSeverity.CRITICAL,
                title="Pulse: Medical surge protocol — triage sites deploying",
                description=(
                    f"Activate mass casualty incident (MCI) protocols for {place}. "
                    f"Deploying {max(2, int(mag))} field triage sites. "
                    f"Requesting mutual aid from neighboring jurisdictions. "
                    f"Blood bank and pharmaceutical supplies mobilized."
                ),
                affected_agents=["Pulse", "Overwatch"],
                delay_seconds=DEMO_DELAY,
            )
        )
        minute += 3

        # 10. Resource deployment
        events.append(
            MissionEvent(
                timestamp=_stagger_ts(base_ms, minute),
                event_type="resource_deployment",
                severity=EventSeverity.HIGH,
                title="Atlas: Resource deployment — supply chain activated",
                description=(
                    f"Pre-positioned disaster supplies being mobilized for {place}. "
                    f"Water, food, shelter materials en route. "
                    f"Helicopter LZ established at nearest viable staging area. "
                    f"ETA for first supply drop: {max(15, int(60 - mag * 5))} minutes."
                ),
                affected_agents=["Atlas", "Overwatch"],
                delay_seconds=DEMO_DELAY,
            )
        )
        minute += 3

        # 11. Communication blackout
        events.append(
            MissionEvent(
                timestamp=_stagger_ts(base_ms, minute),
                event_type="comm_status",
                severity=EventSeverity.HIGH,
                title="Communication infrastructure degraded",
                description=(
                    f"Cell towers and landline infrastructure in {place} region severely damaged. "
                    f"Estimated {int(30 + mag * 5)}% of communication nodes offline. "
                    f"Deploying satellite uplink and mesh network nodes. "
                    f"HAM radio operators activated as backup."
                ),
                affected_agents=["Sentinel", "Atlas", "Overwatch"],
                delay_seconds=DEMO_DELAY,
            )
        )
        minute += 2

        # 12. Evacuation coordination
        events.append(
            MissionEvent(
                timestamp=_stagger_ts(base_ms, minute),
                event_type="evacuation_order",
                severity=EventSeverity.CRITICAL,
                title="Evacuation corridors established — civilian movement begins",
                description=(
                    f"Three evacuation corridors activated from {place} high-risk zone. "
                    f"Corridor Alpha (north), Bravo (east), Charlie (south). "
                    f"Traffic control units deployed. Estimated throughput: {int(2000 + mag * 500)} people/hour."
                ),
                affected_agents=["Atlas", "Sentinel", "Pulse"],
                delay_seconds=DEMO_DELAY,
            )
        )
        minute += 3

        # 13. Structural assessment
        damage_pct = int(min(80, 5 + mag * 8))
        events.append(
            MissionEvent(
                timestamp=_stagger_ts(base_ms, minute),
                event_type="structural_assessment",
                severity=EventSeverity.HIGH,
                title=f"Structural assessment: ~{damage_pct}% of buildings at risk",
                description=(
                    f"Rapid structural assessment of {place} impact zone estimates "
                    f"{damage_pct}% of buildings have sustained moderate to severe damage. "
                    f"Collapse risk remains high for pre-2000 construction. "
                    f"Aegis monitoring for secondary collapse potential."
                ),
                affected_agents=["Sentinel", "Aegis"],
                delay_seconds=DEMO_DELAY,
            )
        )
        minute += 3

        # 14. Aftershocks
        for idx, secondary in enumerate(secondaries[:6]):
            offset_min = minute + idx * 3
            events.append(
                MissionEvent(
                    timestamp=_stagger_ts(base_ms, offset_min),
                    event_type="aftershock",
                    severity=_severity_for_magnitude(secondary.magnitude),
                    title=f"Seismic swarm: M{secondary.magnitude:.1f} — {secondary.place}",
                    description=(
                        f"Additional M{secondary.magnitude:.1f} earthquake detected at {secondary.place}, "
                        f"depth {secondary.depth_km:.0f}km. "
                        f"Seismic instability compounding. "
                        f"Structures weakened by primary event face renewed collapse risk."
                    ),
                    affected_agents=["Aegis", "Sentinel", "Atlas"],
                    delay_seconds=DEMO_DELAY,
                )
            )
        minute += max(3 * len(secondaries[:6]), 3)

        # 15. Weather
        if weather and weather.risk_factors:
            risk_text = "; ".join(weather.risk_factors[:3])
            events.append(
                MissionEvent(
                    timestamp=_stagger_ts(base_ms, minute),
                    event_type="weather_alert",
                    severity=EventSeverity.HIGH
                    if len(weather.risk_factors) >= 2
                    else EventSeverity.MEDIUM,
                    title=f"Weather conditions: {weather.description} ({weather.temperature_c}C)",
                    description=(
                        f"Active weather risk factors: {risk_text}. "
                        f"Wind: {weather.wind_speed_ms:.0f}m/s. Visibility: {weather.visibility_m}m. "
                        f"Adjusting operations for conditions."
                    ),
                    affected_agents=["Aegis", "Atlas", "Pulse"],
                    metadata=context.get("weather", {}),
                    delay_seconds=DEMO_DELAY,
                )
            )
            minute += 3

        # 16. Logistics bottleneck
        events.append(
            MissionEvent(
                timestamp=_stagger_ts(base_ms, minute),
                event_type="logistics_bottleneck",
                severity=EventSeverity.HIGH,
                title="Atlas: Logistics bottleneck — rerouting supply chain",
                description=(
                    f"Primary logistics corridor to {place} congested. "
                    f"Airlift capacity being maximized. Ground convoy rerouted through secondary roads. "
                    f"Fuel and medical supplies prioritized. Requesting additional heavy-lift helicopters."
                ),
                affected_agents=["Atlas", "Overwatch"],
                delay_seconds=DEMO_DELAY,
            )
        )
        minute += 3

        # 17. Aegis risk assessment
        events.append(
            MissionEvent(
                timestamp=_stagger_ts(base_ms, minute),
                event_type="risk_assessment",
                severity=EventSeverity.HIGH,
                title="Aegis: Comprehensive risk matrix updated",
                description=(
                    f"Aegis has updated the full risk matrix for {place}. "
                    f"Primary risks: structural collapse ({damage_pct}% buildings), "
                    f"potential aftershock sequence, communication degradation. "
                    f"Secondary risks: landslides on steep terrain, hazardous material release. "
                    f"Confidence level: {int(75 + mag * 2)}%."
                ),
                affected_agents=["Aegis", "Overwatch"],
                delay_seconds=DEMO_DELAY,
            )
        )
        minute += 3

        # 18. Water/sewer infrastructure
        events.append(
            MissionEvent(
                timestamp=_stagger_ts(base_ms, minute),
                event_type="utilities_disrupted",
                severity=EventSeverity.MEDIUM,
                title="Water and sewer systems compromised",
                description=(
                    f"Municipal water treatment and distribution systems in {place} are compromised. "
                    f"Boil-water advisory issued. Sewer line breaks detected in {int(2 + mag)} locations. "
                    f"Emergency water distribution points being established."
                ),
                affected_agents=["Atlas", "Pulse"],
                delay_seconds=DEMO_DELAY,
            )
        )
        minute += 3

        # 19. Rescue window warning
        events.append(
            MissionEvent(
                timestamp=_stagger_ts(base_ms, minute),
                event_type="rescue_window",
                severity=EventSeverity.CRITICAL,
                title="72-hour rescue window closing fast",
                description=(
                    f"Survival probability drops sharply after 72 hours. "
                    f"Concentrating all resources on highest-probability collapse sites. "
                    f"Current extraction rate: {int(10 + mag * 3)} survivors/hour."
                ),
                affected_agents=all_agents,
                delay_seconds=DEMO_DELAY,
            )
        )
        minute += 3

        # 20. Power grid status
        events.append(
            MissionEvent(
                timestamp=_stagger_ts(base_ms, minute),
                event_type="power_grid",
                severity=EventSeverity.HIGH,
                title="Power grid failure — backup generators deployed",
                description=(
                    f"Regional power grid serving {place} has failed. "
                    f"Backup generators activated at hospitals and command centers. "
                    f"Fuel resupply convoys dispatched. Solar charging stations being set up for field ops."
                ),
                affected_agents=["Atlas", "Sentinel"],
                delay_seconds=DEMO_DELAY,
            )
        )
        minute += 3

        # 21. Refugee shelter
        events.append(
            MissionEvent(
                timestamp=_stagger_ts(base_ms, minute),
                event_type="shelter_status",
                severity=EventSeverity.HIGH,
                title="Emergency shelters at capacity — overflow protocol",
                description=(
                    f"Emergency shelters near {place} are at {int(80 + mag * 2)}% capacity. "
                    f"Overflow shelters being activated at {int(2 + mag)} secondary locations. "
                    f"Estimated displaced persons: {int(15000 + mag * 5000):,}. "
                    f"Humanitarian aid coordination initiated."
                ),
                affected_agents=["Atlas", "Pulse"],
                delay_seconds=DEMO_DELAY,
            )
        )
        minute += 3

        # 22. Fire risk
        events.append(
            MissionEvent(
                timestamp=_stagger_ts(base_ms, minute),
                event_type="fire_risk",
                severity=EventSeverity.HIGH,
                title="Fire outbreak risk elevated — gas leaks detected",
                description=(
                    f"Multiple gas line ruptures reported across {place}. "
                    f"Fire risk critically elevated. Fire suppression teams pre-positioned. "
                    f"Evacuation zones expanded to include gas leak corridors. "
                    f"Aegis monitoring atmospheric sensors for hazardous gas concentrations."
                ),
                affected_agents=["Aegis", "Atlas", "Sentinel"],
                delay_seconds=DEMO_DELAY,
            )
        )
        minute += 3

        # 23. International aid
        events.append(
            MissionEvent(
                timestamp=_stagger_ts(base_ms, minute),
                event_type="mutual_aid",
                severity=EventSeverity.MEDIUM,
                title="International mutual aid — response teams inbound",
                description=(
                    f"International disaster response teams have been activated for {place}. "
                    f"USAR teams, medical units, and logistics support arriving within {int(6 + mag)} hours. "
                    f"Coordination center established to integrate international resources."
                ),
                affected_agents=["Overwatch", "Atlas"],
                delay_seconds=DEMO_DELAY,
            )
        )
        minute += 3

        # 24. Night operations
        if weather and weather.is_night:
            events.append(
                MissionEvent(
                    timestamp=_stagger_ts(base_ms, minute),
                    event_type="night_ops",
                    severity=EventSeverity.HIGH,
                    title="Night operations — reduced visibility protocols active",
                    description=(
                        f"Nightfall in {place}. Search and rescue operations continuing under "
                        f"artificial lighting. Thermal imaging deployed. "
                        f"Drone reconnaissance active for structural monitoring. "
                        f"Reduced operational tempo — safety protocols tightened."
                    ),
                    affected_agents=all_agents,
                    delay_seconds=DEMO_DELAY,
                )
            )
            minute += 3

        # 25. Situational update
        events.append(
            MissionEvent(
                timestamp=_stagger_ts(base_ms, minute),
                event_type="situation_update",
                severity=EventSeverity.HIGH,
                title="Overwatch: Full situation report — all agents synchronized",
                description=(
                    f"All five AI agents have completed analysis of the M{mag:.1f} event at {place}. "
                    f"Unified mission plan synthesized from USGS seismic data, "
                    f"infrastructure mapping, weather conditions, and resource allocation analysis. "
                    f"Situation stabilized. Continuing 24/7 monitoring."
                ),
                affected_agents=all_agents,
                delay_seconds=DEMO_DELAY,
            )
        )
        minute += 3

        # 26. Mission stabilized (final)
        swarm_note = ""
        if secondaries:
            swarm_note = f" amid {len(secondaries)} seismic swarm events"
        events.append(
            MissionEvent(
                timestamp=_stagger_ts(base_ms, minute),
                event_type="mission_stabilized",
                severity=EventSeverity.HIGH,
                title="Mission plan locked — all agents coordinated",
                description=(
                    f"All five AI agents have analyzed the M{mag:.1f} event at {place}{swarm_note}. "
                    f"Unified mission plan synthesized. All systems operational. "
                    f"Continuing real-time monitoring and response coordination."
                ),
                affected_agents=all_agents,
                delay_seconds=DEMO_DELAY,
            )
        )

        swarm_count = len(secondaries)
        name_suffix = f" ({swarm_count + 1} events)" if swarm_count else ""
        scenario = ScenarioDefinition(
            name=f"Live: M{mag:.1f} — {place}{name_suffix}",
            description=(
                f"Live USGS data: M{mag:.1f} earthquake at {place}. "
                f"Depth {primary.depth_km:.0f}km, alert level {primary.alert_level or 'yellow'}. "
                + (
                    f"Seismic swarm: {swarm_count} additional events. "
                    if swarm_count
                    else ""
                )
                + f"Five AI agents coordinating real-time disaster response."
            ),
            agents=["Overwatch", "Sentinel", "Atlas", "Pulse", "Aegis"],
            event_count=len(events),
            events=events,
            context=context,
        )

        _save_cache(scenario)
        return scenario
