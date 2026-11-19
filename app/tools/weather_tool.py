"""Weather tool — Phase 6.

Fetches current + 3-day forecast from Open-Meteo (free, no API key required).
Steps:
  1. Resolve location name → (lat, lon) via Open-Meteo Geocoding API.
  2. Fetch weather variables useful for farming from the Forecast API —
     or, when Open-Meteo refuses (it rate-limits the shared IPs of free
     hosts like Render), from MET Norway's Locationforecast instead.
  3. Return a structured dict AND a formatted English summary string.
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timedelta
from typing import Optional

import requests

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

# Forecasts barely change within a quarter of an hour, and farmers ask about
# the same few places again and again: reuse them instead of calling out.
_FORECAST_TTL = 15 * 60  # seconds
_forecasts: dict[tuple[float, float], tuple[float, dict]] = {}


_COORDS = re.compile(r"^\s*(-?\d{1,2}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)\s*$")


def _parse_coords(location: str) -> Optional[tuple[float, float]]:
    """'18.5204, 73.8567' (from the 📍 button) → (lat, lon)."""
    m = _COORDS.match(location or "")
    if not m:
        return None
    lat, lon = float(m.group(1)), float(m.group(2))
    return (lat, lon) if -90 <= lat <= 90 and -180 <= lon <= 180 else None


def _search_place(name: str) -> list[dict]:
    resp = requests.get(
        GEOCODING_API_URL,
        params={"name": name, "count": 10, "language": "en", "format": "json"},
        timeout=_REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json().get("results", []) or []


_places: dict[str, Optional[tuple[float, float, str]]] = {}


class GeocodingUnavailable(Exception):
    """The place lookup service could not be reached (not: place unknown)."""


def _geocode(location: str) -> Optional[tuple[float, float, str]]:
    """Return (lat, lon, resolved_name) for a location string, or None.

    Farmers are in India, so an Indian match wins over a same-named town
    abroad. "Shirur, Pune" is retried as "Shirur" (the geocoder matches place
    names only). Cached: a place's coordinates are stable, so repeat lookups
    (very common — farmers re-ask about the same village) skip the network.
    A failed request raises GeocodingUnavailable and is not cached — a
    network hiccup must not leave a real village "not found".
    """
    if location in _places:
        return _places[location]
    try:
        candidates = [location] + [p.strip() for p in location.split(",")[:1]
                                   if "," in location and p.strip()]
        results = []
        for name in candidates:
            results = _search_place(name)
            if results:
                break
    except Exception as exc:
        logger.error("Geocoding error for '%s': %s", location, exc)
        raise GeocodingUnavailable(str(exc)) from exc
    if not results:
        logger.warning("Geocoding found no results for '%s'", location)
        found = None
    else:
        r = next((x for x in results if x.get("country_code") == "IN"), results[0])
        name = r.get("name", location)
        region = r.get("admin1", "") if r.get("country_code") == "IN" else r.get("country", "")
        display = f"{name}, {region}" if region else name
        found = (float(r["latitude"]), float(r["longitude"]), display)
    if len(_places) > 512:
        _places.clear()
    _places[location] = found
    return found


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
        return {**resp.json(), "source": "Open-Meteo"}
    except Exception as exc:
        logger.error("Open-Meteo forecast error: %s", exc)
        return None


# ── Fallback: MET Norway Locationforecast (free, no key, global) ─────────────
_MET_URL = "https://api.met.no/weatherapi/locationforecast/2.0/complete"
# MET Norway's terms ask every client to identify itself.
_MET_HEADERS = {"User-Agent": "Multilingual-Agri-AI-Agent/1.0 "
                              "github.com/sehscape/Multilingual-Agri-AI-Agent"}
_MET_SKY = {"clearsky": 0, "fair": 1, "partlycloudy": 2, "cloudy": 3, "fog": 45}


def _met_code(symbol: Optional[str]) -> int:
    """MET Norway symbol ('lightrainshowers_day') → nearest WMO weather code,
    so one formatter and one set of advisories serve both providers."""
    s = (symbol or "").split("_")[0]
    if "thunder" in s:
        return 95
    if s in _MET_SKY:
        return _MET_SKY[s]
    heavy, light = s.startswith("heavy"), s.startswith("light")
    if "snow" in s:
        return 75 if heavy else 71 if light else 73
    if "rain" in s or "sleet" in s:
        if "showers" in s:
            return 82 if heavy else 80 if light else 81
        return 65 if heavy else 61 if light else 63
    return -1


def _utc_offset(lat: float, lon: float) -> timedelta:
    """Local time for grouping the forecast into days: IST inside India,
    else the nearest whole hour by longitude (good enough for day buckets)."""
    if 6 <= lat <= 37 and 68 <= lon <= 98:
        return timedelta(hours=5, minutes=30)
    return timedelta(hours=round(lon / 15))


def _fetch_met_norway(lat: float, lon: float) -> Optional[dict]:
    """The same farming variables from MET Norway, reshaped to look like an
    Open-Meteo response. MET gives no rain probability outside the Nordics,
    so that field is left empty."""
    try:
        resp = requests.get(_MET_URL, params={"lat": round(lat, 4), "lon": round(lon, 4)},
                            headers=_MET_HEADERS, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        series = resp.json()["properties"]["timeseries"]
    except Exception as exc:
        logger.error("MET Norway forecast error: %s", exc)
        return None
    if not series:
        return None

    offset = _utc_offset(lat, lon)
    times = [datetime.fromisoformat(s["time"].replace("Z", "+00:00")) for s in series]
    days: dict[str, dict] = {}
    for i, step in enumerate(series):
        data = step["data"]
        inst = data["instant"]["details"]
        gap = (times[i + 1] - times[i]) if i + 1 < len(times) else timedelta(hours=6)
        # Hourly steps carry next_1_hours, later 6-hourly steps next_6_hours:
        # take the period that matches the gap, so no rain is counted twice.
        period = data.get("next_1_hours") if gap <= timedelta(hours=1) else data.get("next_6_hours")
        period = period or data.get("next_1_hours") or data.get("next_6_hours") or {}
        details = period.get("details", {})
        day = days.setdefault((times[i] + offset).date().isoformat(),
                              {"temps": [], "rain": 0.0, "wind": [], "codes": []})
        day["temps"] += [inst.get("air_temperature")]
        day["temps"] += [details.get(k) for k in ("air_temperature_max", "air_temperature_min")]
        day["rain"] += details.get("precipitation_amount") or 0.0
        day["wind"].append((inst.get("wind_speed") or 0.0) * 3.6)  # m/s → km/h
        day["codes"].append(_met_code(period.get("summary", {}).get("symbol_code")))

    now = series[0]["data"]
    inst = now["instant"]["details"]
    first_hour = now.get("next_1_hours") or now.get("next_6_hours") or {}
    dates = sorted(days)
    daily = {"time": dates, "weather_code": [], "temperature_2m_max": [],
             "temperature_2m_min": [], "precipitation_sum": [],
             "precipitation_probability_max": [], "wind_speed_10m_max": []}
    for d in dates:
        temps = [t for t in days[d]["temps"] if t is not None]
        daily["weather_code"].append(max(days[d]["codes"]))  # the day's most significant weather
        daily["temperature_2m_max"].append(round(max(temps), 1) if temps else None)
        daily["temperature_2m_min"].append(round(min(temps), 1) if temps else None)
        daily["precipitation_sum"].append(round(days[d]["rain"], 1))
        daily["wind_speed_10m_max"].append(round(max(days[d]["wind"]), 1))
    temp = inst.get("air_temperature")
    return {
        "source": "MET Norway",
        "current": {
            "temperature_2m": temp,
            "relative_humidity_2m": inst.get("relative_humidity"),
            "apparent_temperature": inst.get("apparent_air_temperature", temp),
            "precipitation": first_hour.get("details", {}).get("precipitation_amount", 0.0),
            "weather_code": _met_code(first_hour.get("summary", {}).get("symbol_code")),
            "wind_speed_10m": round((inst.get("wind_speed") or 0.0) * 3.6, 1),
        },
        "daily": daily,
    }


def _forecast(lat: float, lon: float) -> Optional[dict]:
    """Open-Meteo first, MET Norway if it refuses; reused for a quarter hour."""
    key = (round(lat, 2), round(lon, 2))
    hit = _forecasts.get(key)
    if hit and time.time() - hit[0] < _FORECAST_TTL:
        return hit[1]
    data = _fetch_forecast(lat, lon) or _fetch_met_norway(lat, lon)
    if data is not None:
        if len(_forecasts) > 512:
            _forecasts.clear()
        _forecasts[key] = (time.time(), data)
    return data


def _format_weather(location_display: str, data: dict) -> str:
    """Convert a forecast (Open-Meteo shape) into a farming-relevant text summary."""
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
        rain_prob = precip_probs[i] if i < len(precip_probs) else None
        rain_mm = precip_sums[i] if i < len(precip_sums) else "N/A"
        chance = f" ({rain_prob}% chance)" if rain_prob is not None else ""
        lines.append(
            f"  {dates[i]}: {desc}, "
            f"{min_temps[i] if i < len(min_temps) else '?'}–"
            f"{max_temps[i] if i < len(max_temps) else '?'}°C, "
            f"Rain: {rain_mm}mm{chance}, "
            f"Wind: {wind_maxs[i] if i < len(wind_maxs) else '?'} km/h"
        )
    if data.get("source"):
        lines.append(f"  Forecast source: {data['source']}")

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


def forecast_card(raw: dict, summary: str = "") -> dict:
    """The forecast as plain numbers for a weather card on the web app:
    {place, gps, source, now: {...}, days: [{date, code, min, max, rain_mm,
    rain_pct, wind}, ...]} — today first. `summary` supplies the place name."""
    m = re.search(r"Weather for (.+)", summary or "")
    place = m.group(1).strip() if m else ""
    gps = place.startswith("the farmer's location")
    cur, daily = raw.get("current", {}) or {}, raw.get("daily", {}) or {}

    def col(key: str, i: int):
        values = daily.get(key) or []
        return values[i] if i < len(values) else None

    days = [{"date": date, "code": col("weather_code", i),
             "min": col("temperature_2m_min", i), "max": col("temperature_2m_max", i),
             "rain_mm": col("precipitation_sum", i),
             "rain_pct": col("precipitation_probability_max", i),
             "wind": col("wind_speed_10m_max", i)}
            for i, date in enumerate((daily.get("time") or [])[:4])]
    code = cur.get("weather_code", -1)
    return {
        "place": "" if gps else place,
        "gps": gps,
        "source": raw.get("source", "Open-Meteo"),
        "now": {"temp": cur.get("temperature_2m"), "feels": cur.get("apparent_temperature"),
                "humidity": cur.get("relative_humidity_2m"), "wind": cur.get("wind_speed_10m"),
                "rain_mm": cur.get("precipitation"), "code": code,
                "desc": _WMO_DESCRIPTIONS.get(code, "")},
        "days": days,
    }


def get_weather_context(location: Optional[str]) -> tuple[Optional[dict], str]:
    """
    Main entry point for the weather tool.

    Returns (raw_data_dict, formatted_english_summary).
    raw_data_dict is None on failure; the string always contains a message.
    """
    if not location:
        return None, "No location specified. Please provide a village, city, or district name."

    coords = _parse_coords(location)
    if coords:
        lat, lon = coords
        display = f"the farmer's location ({lat:.2f}, {lon:.2f})"
    else:
        try:
            geo = _geocode(location)
        except GeocodingUnavailable:
            return None, (f"Weather data is temporarily unavailable for {location}. "
                          "Please try again later.")
        if geo is None:
            return None, (f"Could not find location '{location}'. "
                          "Please check the spelling or try a nearby city.")
        lat, lon, display = geo
    logger.info("Resolved '%s' → %s (%.4f, %.4f)", location, display, lat, lon)

    raw = _forecast(lat, lon)
    if raw is None:
        return None, f"Weather data is temporarily unavailable for {display}. Please try again later."

    summary = _format_weather(display, raw)
    logger.info("Weather fetched successfully for %s", display)
    return raw, summary
