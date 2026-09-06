"""Crop knowledge tool — Phase 5.

Loads crop JSON files from data/crops/ and returns stage-specific
advisory context for the LLM given a crop name and growth stage in days.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from app.config import CROPS_DIR
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Canonical name → JSON filename (no extension)
_CROP_FILES: dict[str, str] = {
    "wheat": "wheat",
    "rice": "rice",
    "paddy": "rice",
    "onion": "onion",
    "tomato": "tomato",
    "cotton": "cotton",
    "maize": "maize",
    "corn": "maize",
}

# Local-language name → canonical English name
_LOCAL_NAME_MAP: dict[str, str] = {
    # Hindi
    "गेहूं": "wheat", "गेहू": "wheat",
    "धान": "rice", "चावल": "rice",
    "प्याज": "onion", "कांदा": "onion",
    "टमाटर": "tomato",
    "कपास": "cotton",
    "मक्का": "maize", "मकई": "maize",
    # Marathi
    "गव्हू": "wheat",
    "भात": "rice",
    "टोमॅटो": "tomato",
    "कापूस": "cotton",
    "मका": "maize",
    # Punjabi
    "ਕਣਕ": "wheat",
    "ਝੋਨਾ": "rice", "ਧਾਨ": "rice",
    "ਪਿਆਜ਼": "onion",
    "ਟਮਾਟਰ": "tomato",
    "ਕਪਾਹ": "cotton",
    "ਮੱਕੀ": "maize",
}

_cache: dict[str, dict] = {}


def _load_crop(canonical: str) -> Optional[dict]:
    if canonical in _cache:
        return _cache[canonical]
    filename = _CROP_FILES.get(canonical)
    if not filename:
        return None
    path = Path(CROPS_DIR) / f"{filename}.json"
    if not path.exists():
        logger.warning("Crop JSON not found: %s", path)
        return None
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    _cache[canonical] = data
    return data


def _resolve_crop_name(raw_name: str) -> Optional[str]:
    """Resolve raw crop name (English or local language) to canonical name."""
    if not raw_name:
        return None
    lower = raw_name.lower().strip()
    # Direct English match
    if lower in _CROP_FILES:
        return lower
    # Local language match
    return _LOCAL_NAME_MAP.get(raw_name.strip())


def _find_stage(crop_data: dict, days: Optional[int]) -> Optional[dict]:
    """Return the growth stage dict that matches the given day count."""
    if days is None:
        return None
    for stage in crop_data.get("stages", []):
        lo, hi = stage["days_range"]
        if lo <= days <= hi:
            return stage
    # If beyond last stage, return last
    stages = crop_data.get("stages", [])
    return stages[-1] if stages else None


def get_crop_context(crop_name: Optional[str], crop_stage_days: Optional[int]) -> str:
    """
    Main entry point for the crop tool.

    Returns a formatted string summarising crop knowledge for the given
    crop and growth stage. Returns a 'not found' message if the crop is
    not in the knowledge base.
    """
    if not crop_name:
        return "No crop specified by the farmer."

    canonical = _resolve_crop_name(crop_name)
    if not canonical:
        return (
            f"Crop '{crop_name}' is not in the knowledge base. "
            "Available crops: wheat, rice, onion, tomato, cotton, maize."
        )

    data = _load_crop(canonical)
    if not data:
        return f"Knowledge base file for '{canonical}' could not be loaded."

    lines = [
        f"Crop          : {data['name'].title()}",
        f"Sowing season : {data.get('sowing_season', 'N/A')}",
        f"Harvest season: {data.get('harvest_season', 'N/A')}",
        f"Soil          : {data.get('soil', 'N/A')}",
        f"Total duration: {data.get('total_duration_days', '?')} days",
    ]

    if crop_stage_days is not None:
        lines.append(f"Current age   : {crop_stage_days} days")
        stage = _find_stage(data, crop_stage_days)
        if stage:
            lines += [
                "",
                f"=== Current Stage: {stage['name']} (days {stage['days_range'][0]}–{stage['days_range'][1]}) ===",
                f"Description   : {stage['description']}",
                f"Irrigation    : {stage['irrigation']}",
                f"Fertilizer    : {stage['fertilizer']}",
                f"Watch for     : {', '.join(stage.get('watch_for', []))}",
                f"Tips          : {' | '.join(stage.get('tips', []))}",
            ]

    # Common pests and diseases (summary)
    pests = data.get("common_pests", [])
    diseases = data.get("common_diseases", [])
    if pests:
        lines.append("")
        lines.append("Common pests:")
        for p in pests:
            lines.append(f"  • {p['name']}: {p['symptoms']} → {p['control']}")
    if diseases:
        lines.append("")
        lines.append("Common diseases:")
        for d in diseases:
            lines.append(f"  • {d['name']}: {d['symptoms']} → {d['control']}")

    return "\n".join(lines)
