from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass


_OVERPASS_URL = "https://overpass-api.de/api/interpreter"


@dataclass(frozen=True)
class Hospital:
    name: str
    lat: float
    lon: float
    beds: int | None
    emergency: bool


@dataclass(frozen=True)
class Road:
    name: str
    highway_type: str
    length_km: float


@dataclass(frozen=True)
class InfrastructureSummary:
    hospital_count: int
    hospitals: list[Hospital]
    major_roads: list[Road]
    building_count: int
    total_beds: int | None
    population_estimate: int | None


def _overpass_query(query: str) -> dict:
    encoded = urllib.parse.urlencode({"data": query})
    url = f"{_OVERPASS_URL}?{encoded}"
    req = urllib.request.Request(url, headers={"User-Agent": "MissionControl/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def fetch_infrastructure(
    lat: float, lon: float, radius_km: float = 50.0
) -> InfrastructureSummary:
    radius_m = int(radius_km * 1000)

    hospitals_query = f"""
    [out:json][timeout:25];
    (
      node["amenity"="hospital"](around:{radius_m},{lat},{lon});
      way["amenity"="hospital"](around:{radius_m},{lat},{lon});
    );
    out center tags;
    """

    roads_query = f"""
    [out:json][timeout:25];
    way["highway"~"^(motorway|trunk|primary)$"](around:{radius_m},{lat},{lon});
    out tags;
    """

    buildings_query = f"""
    [out:json][timeout:25];
    (
      way["building"](around:{radius_m},{lat},{lon});
      relation["building"](around:{radius_m},{lat},{lon});
    );
    out ids;
    """

    hospitals: list[Hospital] = []
    try:
        data = _overpass_query(hospitals_query)
        for elem in data.get("elements", []):
            tags = elem.get("tags", {})
            center = elem.get("center", {})
            hospitals.append(
                Hospital(
                    name=tags.get("name", "Unnamed hospital"),
                    lat=center.get("lat", elem.get("lat", 0.0)),
                    lon=center.get("lon", elem.get("lon", 0.0)),
                    beds=_safe_int(tags.get("beds")),
                    emergency=tags.get("emergency") == "yes"
                    or "emergency" in tags.get("healthcare:speciality", ""),
                )
            )
    except Exception:
        pass

    roads: list[Road] = []
    try:
        data = _overpass_query(roads_query)
        for elem in data.get("elements", []):
            tags = elem.get("tags", {})
            roads.append(
                Road(
                    name=tags.get("name", f"Unnamed {tags.get('highway', 'road')}"),
                    highway_type=tags.get("highway", "unknown"),
                    length_km=0.0,
                )
            )
    except Exception:
        pass

    building_count = 0
    try:
        data = _overpass_query(buildings_query)
        building_count = len(data.get("elements", []))
    except Exception:
        pass

    total_beds = sum(h.beds for h in hospitals if h.beds) if hospitals else None

    return InfrastructureSummary(
        hospital_count=len(hospitals),
        hospitals=hospitals[:20],
        major_roads=roads[:20],
        building_count=building_count,
        total_beds=total_beds,
        population_estimate=None,
    )


def _safe_int(val: str | None) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


import urllib.parse
