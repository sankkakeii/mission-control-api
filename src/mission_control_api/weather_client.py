from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass


_OPENWEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"


@dataclass(frozen=True)
class WeatherConditions:
    temperature_c: float
    humidity_percent: int
    wind_speed_ms: float
    wind_gust_ms: float | None
    description: str
    rain_1h_mm: float
    rain_3h_mm: float
    visibility_m: int
    is_night: bool
    risk_factors: list[str]


def fetch_weather(lat: float, lon: float) -> WeatherConditions | None:
    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        return None

    url = f"{_OPENWEATHER_URL}?lat={lat}&lon={lon}&appid={api_key}&units=metric"
    req = urllib.request.Request(url, headers={"User-Agent": "MissionControl/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return None

    main = data.get("main", {})
    wind = data.get("wind", {})
    rain = data.get("rain", {})
    weather_desc = data.get("weather", [{}])
    sys_data = data.get("sys", {})

    sunset = sys_data.get("sunset", 0)
    sunrise = sys_data.get("sunrise", 0)
    import time

    now = int(time.time())
    is_night = now > sunset or now < sunrise if sunset and sunrise else False

    rain_1h = rain.get("1h", 0.0)
    rain_3h = rain.get("3h", 0.0)
    wind_speed = wind.get("speed", 0.0)
    wind_gust = wind.get("gust")
    visibility = data.get("visibility", 10000)

    risk_factors: list[str] = []
    if rain_1h > 5.0 or rain_3h > 15.0:
        risk_factors.append("Heavy rain — mudslide and flood risk elevated")
    elif rain_1h > 1.0:
        risk_factors.append(
            "Moderate rain — affects rescue operations and road conditions"
        )
    if wind_speed > 15.0:
        risk_factors.append(
            f"High winds ({wind_speed:.0f}m/s) — helicopter operations restricted"
        )
    if wind_gust and wind_gust > 20.0:
        risk_factors.append(
            f"Wind gusts to {wind_gust:.0f}m/s — structural instability risk"
        )
    if visibility < 1000:
        risk_factors.append(
            f"Low visibility ({visibility}m) — aerial reconnaissance limited"
        )
    if is_night:
        risk_factors.append("Nighttime — search and rescue operations degraded")

    temp = main.get("temp", 20.0)
    if temp < 0:
        risk_factors.append(
            f"Cold conditions ({temp:.0f}C) — exposure risk for trapped survivors"
        )
    elif temp > 35:
        risk_factors.append(
            f"Extreme heat ({temp:.0f}C) — dehydration risk for survivors and responders"
        )

    return WeatherConditions(
        temperature_c=round(temp, 1),
        humidity_percent=main.get("humidity", 0),
        wind_speed_ms=wind_speed,
        wind_gust_ms=wind_gust,
        description=weather_desc[0].get("description", "unknown")
        if weather_desc
        else "unknown",
        rain_1h_mm=rain_1h,
        rain_3h_mm=rain_3h,
        visibility_m=visibility,
        is_night=is_night,
        risk_factors=risk_factors,
    )
