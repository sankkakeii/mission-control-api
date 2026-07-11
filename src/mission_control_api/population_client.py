from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass


_WorldPop_URL = "https://api.worldpop.org/v1/datasets"


@dataclass(frozen=True)
class PopulationEstimate:
    population: int
    density_per_sqkm: float
    source: str


def fetch_population(
    lat: float, lon: float, radius_km: float = 50.0
) -> PopulationEstimate | None:
    url = (
        f"https://api.worldpop.org/v1/datasets/wpp2022?"
        f"lat={lat}&long={lon}&radius={int(radius_km)}&verbose=false"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "MissionControl/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        if "data" in data:
            pop = data["data"].get("population", 0)
            area_sqkm = 3.14159 * radius_km**2
            density = pop / area_sqkm if area_sqkm > 0 else 0.0
            return PopulationEstimate(
                population=int(pop),
                density_per_sqkm=round(density, 1),
                source="WorldPop",
            )
    except Exception:
        pass

    return _estimate_from_coordinates(lat, lon)


def _estimate_from_coordinates(lat: float, lon: float) -> PopulationEstimate | None:
    regions = {
        "South Sandwich Islands": (0, 0.001),
        "Caracas": (3_200_000, 4500.0),
        "Istanbul": (15_800_000, 2800.0),
        "Mexico City": (21_800_000, 6000.0),
        "Tokyo": (37_400_000, 6100.0),
        "Christchurch": (395_000, 250.0),
        "Nepal": (30_000_000, 200.0),
        "Haiti": (11_600_000, 400.0),
        "Chile": (19_500_000, 25.0),
        "Iran": (87_000_000, 52.0),
        "Turkey": (85_000_000, 110.0),
        "Indonesia": (275_000_000, 150.0),
        "Philippines": (115_000_000, 368.0),
    }
    return None
