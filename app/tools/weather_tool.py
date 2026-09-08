"""Weather tool — Phase 6.

Fetches current + 3-day forecast from Open-Meteo (free, no API key required).
Steps:
  1. Resolve location name → (lat, lon) via Open-Meteo Geocoding API.
  2. Fetch weather variables useful for farming from the Forecast API.
  3. Return a structured dict AND a formatted English summary string.
"""
from __future__ import annotations

import requests
from functools import lru_cache
from typing import Optional

from app.config import GEOCODING_API_URL, WEATHER_API_URL
from app.utils.logging import get_logger

logger = get_logger(__name__)

# WMO weather interpretation codes → human-readable
_WMO_DESCRIPTIONS: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Foggy", 48: "Icy fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
    77: "Snow grains",
    80: "Slight showers", 81: "Moderate showers", 82: "Violent showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}

_REQUEST_TIMEOUT = 10  # seconds


@lru_cache(maxsize=256)
def _geocode(location: str) -> Optional[tuple[float, float, str]]:
    """Return (lat, lon, resolved_name) for a location string, or None.

    Cached: a place's coordinates are stable, so repeat lookups (very common —
    farmers re-ask about the same village) skip the network round-trip.
    """
    try:
        resp = requests.get(
            GEOCODING_API_URL,
            params={"name": location, "count": 1, "language": "en", "format": "json"},
            timeout=_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            logger.warning("Geocoding found no results for '%s'", location)
            return None
        r = results[0]
        name = r.get("name", location)
        country = r.get("country", "")
        display = f"{name}, {country}" if country else name
        return float(r["latitude"]), float(r["longitude"]), display
    except Exception as exc:
        logger.error("Geocoding error for '%s': %s", location, exc)
        return None


def _fetch_forecast(lat: float, lon: float) -> Optional[dict]:
    """Fetch weather data from Open-Meteo Forecast API."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": [
            "temperature_2m",
            "relative_humidity_2m",
            "apparent_temperature",
            "precipitation",
            "weather_code",
            "wind_speed_10m",
        ],
        "daily": [
            "weather_code",
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "precipitation_probability_max",
            "wind_speed_10m_max",
        ],
        "timezone": "auto",
        "forecast_days": 4,
    }
    try:
        resp = requests.get(WEATHER_API_URL, params=params, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.error("Forecast API error: %s", exc)
        return None


def _format_weather(location_display: str, data: dict) -> str:
    """Convert raw Open-Meteo response into a farming-relevant text summary."""
    cur = data.get("current", {})
    daily = data.get("daily", {})

    cur_temp = cur.get("temperature_2m", "N/A")
    cur_feels = cur.get("apparent_temperature", "N/A")
    cur_humidity = cur.get("relative_humidity_2m", "N/A")
    cur_precip = cur.get("precipitation", 0)
    cur_wind = cur.get("wind_speed_10m", "N/A")
    cur_code = cur.get("weather_code", -1)
    cur_desc = _WMO_DESCRIPTIONS.get(cur_code, "Unknown")

    lines = [
        f"Weather for {location_display}",
        f"",
        f"Current conditions:",
        f"  Temperature   : {cur_temp}°C (feels like {cur_feels}°C)",
        f"  Humidity      : {cur_humidity}%",
        f"  Precipitation : {cur_precip} mm",
        f"  Wind speed    : {cur_wind} km/h",
        f"  Condition     : {cur_desc}",
        f"",
        f"3-day forecast:",
    ]

    dates = daily.get("time", [])
    max_temps = daily.get("temperature_2m_max", [])
    min_temps = daily.get("temperature_2m_min", [])
    precip_sums = daily.get("precipitation_sum", [])
    precip_probs = daily.get("precipitation_probability_max", [])
    wind_maxs = daily.get("wind_speed_10m_max", [])
    codes = daily.get("weather_code", [])

    # Skip index 0 (today already shown in current); show next 3 days
    for i in range(1, min(4, len(dates))):
        desc = _WMO_DESCRIPTIONS.get(codes[i] if i < len(codes) else -1, "Unknown")
        rain_prob = precip_probs[i] if i < len(precip_probs) else "N/A"
        rain_mm = precip_sums[i] if i < len(precip_sums) else "N/A"
        lines.append(
            f"  {dates[i]}: {desc}, "
            f"{min_temps[i] if i < len(min_temps) else '?'}–"
            f"{max_temps[i] if i < len(max_temps) else '?'}°C, "
            f"Rain: {rain_mm}mm ({rain_prob}% chance), "
            f"Wind: {wind_maxs[i] if i < len(wind_maxs) else '?'} km/h"
        )

    # Farming advisories
    advisories = _farming_advisories(cur_temp, cur_humidity, cur_precip, cur_code)
    if advisories:
        lines.append("")
        lines.append("Farming advisories:")
        for adv in advisories:
            lines.append(f"  • {adv}")

    return "\n".join(lines)


def _farming_advisories(
    temp: object, humidity: object, precip: object, weather_code: int
) -> list[str]:
    """Generate simple rule-based farming advisories from current conditions."""
    advisories = []
    try:
        t = float(temp)
        if t > 38:
            advisories.append("Extreme heat — avoid spraying pesticides; ensure irrigation.")
        elif t < 5:
            advisories.append("Near-frost conditions — protect sensitive crops.")
    except (TypeError, ValueError):
        pass

    try:
        h = float(humidity)
        if h > 85:
            advisories.append("High humidity — increased fungal disease risk; monitor crops.")
        elif h < 30:
            advisories.append("Low humidity — consider irrigation to prevent moisture stress.")
    except (TypeError, ValueError):
        pass

    try:
        p = float(precip)
        if p > 20:
            advisories.append("Heavy rainfall — check drainage; delay fertilizer application.")
        elif p > 5:
            advisories.append("Moderate rain — good for soil moisture; hold off on irrigation.")
    except (TypeError, ValueError):
        pass

    if weather_code in (95, 96, 99):
        advisories.append("Thunderstorm risk — keep people and equipment away from open fields.")

    return advisories


def get_weather_context(location: Optional[str]) -> tuple[Optional[dict], str]:
    """
    Main entry point for the weather tool.

    Returns (raw_data_dict, formatted_english_summary).
    raw_data_dict is None on failure; the string always contains a message.
    """
    if not location:
        return None, "No location specified. Please provide a village, city, or district name."

    geo = _geocode(location)
    if geo is None:
        return None, f"Could not find location '{location}'. Please check the spelling or try a nearby city."

    lat, lon, display = geo
    logger.info("Resolved '%s' → %s (%.4f, %.4f)", location, display, lat, lon)

    raw = _fetch_forecast(lat, lon)
    if raw is None:
        return None, f"Weather data is temporarily unavailable for {display}. Please try again later."

    summary = _format_weather(display, raw)
    logger.info("Weather fetched successfully for %s", display)
    return raw, summary
