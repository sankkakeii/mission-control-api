from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DataPoint:
    label: str
    value: str
    category: str  # earthquake, infrastructure, weather, population
    keywords: list[str] = field(default_factory=list)


@dataclass
class CitationResult:
    total_data_points: int
    cited_count: int
    citation_score: float  # 0.0-1.0
    cited: list[str]
    missing: list[str]
    cited_categories: dict[str, int]  # category -> count cited
    total_categories: dict[str, int]  # category -> total available


def extract_data_points(context: dict[str, Any] | None) -> list[DataPoint]:
    """Extract all factual data points from scenario context."""
    if not context:
        return []

    points: list[DataPoint] = []

    eq = context.get("earthquake", {})
    if eq:
        if eq.get("magnitude") is not None:
            points.append(
                DataPoint(
                    label=f"M{eq['magnitude']:.1f}",
                    value=str(eq["magnitude"]),
                    category="earthquake",
                    keywords=[
                        "magnitude",
                        "mag",
                        f"m{eq['magnitude']:.1f}",
                        f"m{eq['magnitude']}",
                    ],
                )
            )
        if eq.get("depth_km") is not None:
            points.append(
                DataPoint(
                    label=f"{eq['depth_km']:.0f}km depth",
                    value=str(eq["depth_km"]),
                    category="earthquake",
                    keywords=[
                        "depth",
                        f"{eq['depth_km']:.0f}km",
                        f"{eq['depth_km']} km",
                    ],
                )
            )
        if eq.get("place"):
            points.append(
                DataPoint(
                    label=eq["place"],
                    value=eq["place"],
                    category="earthquake",
                    keywords=[eq["place"].lower()],
                )
            )
        if eq.get("alert_level"):
            points.append(
                DataPoint(
                    label=f"alert {eq['alert_level']}",
                    value=eq["alert_level"],
                    category="earthquake",
                    keywords=[eq["alert_level"].lower(), "alert level", "pager"],
                )
            )
        if eq.get("tsunami"):
            points.append(
                DataPoint(
                    label="tsunami warning active",
                    value="true",
                    category="earthquake",
                    keywords=["tsunami"],
                )
            )

    infra = context.get("infrastructure", {})
    if infra:
        if infra.get("hospital_count") is not None:
            points.append(
                DataPoint(
                    label=f"{infra['hospital_count']} hospitals",
                    value=str(infra["hospital_count"]),
                    category="infrastructure",
                    keywords=[
                        f"{infra['hospital_count']} hospital",
                        "hospital",
                        f"{infra['hospital_count']} facilities",
                    ],
                )
            )
        if infra.get("total_beds") is not None and infra["total_beds"] > 0:
            points.append(
                DataPoint(
                    label=f"{infra['total_beds']} beds",
                    value=str(infra["total_beds"]),
                    category="infrastructure",
                    keywords=[
                        f"{infra['total_beds']} bed",
                        "bed capacity",
                        "beds",
                        "total beds",
                    ],
                )
            )
        if infra.get("building_count") is not None:
            points.append(
                DataPoint(
                    label=f"{infra['building_count']} structures",
                    value=str(infra["building_count"]),
                    category="infrastructure",
                    keywords=[
                        f"{infra['building_count']}",
                        "structures",
                        "buildings",
                        "mapped structures",
                    ],
                )
            )
        roads = infra.get("major_roads", [])
        if roads:
            road_names = [
                r.get("name", "")
                for r in roads[:5]
                if r.get("name") and r["name"] != "Unnamed"
            ]
            if road_names:
                points.append(
                    DataPoint(
                        label=f"{len(roads)} roads ({', '.join(road_names[:3])})",
                        value=str(len(roads)),
                        category="infrastructure",
                        keywords=[name.lower() for name in road_names]
                        + ["roads", "routes", "supply lines"],
                    )
                )

        hospitals = infra.get("hospitals", [])
        if hospitals:
            named = [
                h
                for h in hospitals[:5]
                if h.get("name") and h["name"] != "Unnamed hospital"
            ]
            if named:
                for h in named[:3]:
                    points.append(
                        DataPoint(
                            label=h["name"],
                            value=h["name"],
                            category="infrastructure",
                            keywords=[h["name"].lower()],
                        )
                    )

    weather = context.get("weather", {})
    if weather:
        if weather.get("temperature_c") is not None:
            points.append(
                DataPoint(
                    label=f"{weather['temperature_c']}C",
                    value=str(weather["temperature_c"]),
                    category="weather",
                    keywords=[
                        f"{weather['temperature_c']}c",
                        f"{weather['temperature_c']} c",
                        "temperature",
                        "celsius",
                    ],
                )
            )
        if weather.get("wind_speed_ms") is not None:
            points.append(
                DataPoint(
                    label=f"wind {weather['wind_speed_ms']:.0f}m/s",
                    value=str(weather["wind_speed_ms"]),
                    category="weather",
                    keywords=[
                        f"{weather['wind_speed_ms']:.0f}m/s",
                        f"{weather['wind_speed_ms']:.0f} m/s",
                        "wind",
                        "wind speed",
                    ],
                )
            )
        if weather.get("visibility_m") is not None:
            points.append(
                DataPoint(
                    label=f"visibility {weather['visibility_m']}m",
                    value=str(weather["visibility_m"]),
                    category="weather",
                    keywords=[
                        f"{weather['visibility_m']}m",
                        f"{weather['visibility_m']} m",
                        "visibility",
                    ],
                )
            )
        if weather.get("description"):
            points.append(
                DataPoint(
                    label=weather["description"],
                    value=weather["description"],
                    category="weather",
                    keywords=[weather["description"].lower()],
                )
            )
        if weather.get("is_night"):
            points.append(
                DataPoint(
                    label="nighttime operations",
                    value="night",
                    category="weather",
                    keywords=["night", "darkness", "nighttime", "reduced visibility"],
                )
            )

    swarm = context.get("seismic_swarm", [])
    if swarm:
        points.append(
            DataPoint(
                label=f"{len(swarm)} swarm events",
                value=str(len(swarm)),
                category="earthquake",
                keywords=[
                    f"{len(swarm)} additional",
                    "swarm",
                    "aftershock",
                    f"{len(swarm)} event",
                ],
            )
        )
        for s in swarm[:3]:
            if s.get("magnitude"):
                points.append(
                    DataPoint(
                        label=f"M{s['magnitude']:.1f} aftershock",
                        value=str(s["magnitude"]),
                        category="earthquake",
                        keywords=[f"m{s['magnitude']:.1f}", "aftershock"],
                    )
                )

    return points


def validate_citations(
    analysis: str,
    recommendation: str,
    context: dict[str, Any] | None,
) -> CitationResult:
    """Check how many data points from context are referenced in agent output."""
    data_points = extract_data_points(context)
    if not data_points:
        return CitationResult(
            total_data_points=0,
            cited_count=0,
            citation_score=1.0,
            cited=[],
            missing=[],
            cited_categories={},
            total_categories={},
        )

    combined_text = f"{analysis} {recommendation}".lower()

    cited: list[str] = []
    missing: list[str] = []
    cited_categories: dict[str, int] = {}
    total_categories: dict[str, int] = {}

    for dp in data_points:
        total_categories[dp.category] = total_categories.get(dp.category, 0) + 1
        found = any(kw in combined_text for kw in dp.keywords)
        if found:
            cited.append(dp.label)
            cited_categories[dp.category] = cited_categories.get(dp.category, 0) + 1
        else:
            missing.append(dp.label)

    total = len(data_points)
    cited_count = len(cited)
    score = cited_count / total if total > 0 else 1.0

    return CitationResult(
        total_data_points=total,
        cited_count=cited_count,
        citation_score=round(score, 3),
        cited=cited,
        missing=missing,
        cited_categories=cited_categories,
        total_categories=total_categories,
    )
