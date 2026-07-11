from __future__ import annotations

import urllib.request
import json
from dataclasses import dataclass


_USGS_FEEDS = {
    "significant_day": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_day.geojson",
    "significant_week": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_week.geojson",
    "significant_month": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_month.geojson",
    "4.5_week": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson",
    "all_day": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson",
}


@dataclass(frozen=True)
class USGSEarthquake:
    usgs_id: str
    title: str
    magnitude: float
    place: str
    latitude: float
    longitude: float
    depth_km: float
    timestamp_ms: int
    tsunami: bool
    felt_count: int | None
    alert_level: str | None
    significance: int


def fetch_latest_earthquake(feed: str = "significant_week") -> USGSEarthquake | None:
    url = _USGS_FEEDS.get(feed)
    if not url:
        raise ValueError(
            f"Unknown USGS feed: {feed!r}. Available: {', '.join(_USGS_FEEDS)}"
        )

    req = urllib.request.Request(url, headers={"User-Agent": "MissionControl/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())

    features = data.get("features", [])
    if not features:
        return None

    latest = features[0]
    props = latest["properties"]
    coords = latest["geometry"]["coordinates"]

    return USGSEarthquake(
        usgs_id=latest["id"],
        title=props.get("title", "Unknown earthquake"),
        magnitude=props.get("mag", 0.0),
        place=props.get("place", "Unknown location"),
        latitude=coords[1],
        longitude=coords[0],
        depth_km=coords[2] if len(coords) > 2 else 0.0,
        timestamp_ms=int(props.get("time", 0)),
        tsunami=bool(props.get("tsunami", 0)),
        felt_count=props.get("felt"),
        alert_level=props.get("alert"),
        significance=props.get("sig", 0),
    )


def fetch_earthquakes(feed: str = "4.5_week", limit: int = 10) -> list[USGSEarthquake]:
    url = _USGS_FEEDS.get(feed)
    if not url:
        raise ValueError(f"Unknown USGS feed: {feed!r}")

    req = urllib.request.Request(url, headers={"User-Agent": "MissionControl/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())

    results = []
    for feature in data.get("features", [])[:limit]:
        props = feature["properties"]
        coords = feature["geometry"]["coordinates"]
        results.append(
            USGSEarthquake(
                usgs_id=feature["id"],
                title=props.get("title", "Unknown earthquake"),
                magnitude=props.get("mag", 0.0),
                place=props.get("place", "Unknown location"),
                latitude=coords[1],
                longitude=coords[0],
                depth_km=coords[2] if len(coords) > 2 else 0.0,
                timestamp_ms=int(props.get("time", 0)),
                tsunami=bool(props.get("tsunami", 0)),
                felt_count=props.get("felt"),
                alert_level=props.get("alert"),
                significance=props.get("sig", 0),
            )
        )
    return results
