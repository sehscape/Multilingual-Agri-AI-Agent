"""Crop knowledge tool — Phase 5.

Reads the crop guides in data/crops/ (through app.knowledge) and returns
stage-specific advisory context for the LLM, given a crop name and the
crop's age in days.
"""
from __future__ import annotations

from typing import Optional

from app import knowledge
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _load_crop(canonical: Optional[str]) -> Optional[dict]:
    return knowledge.crop(canonical)


def _resolve_crop_name(raw_name: Optional[str]) -> Optional[str]:
    """A crop name in English or a local language ("paddy", "ਝੋਨਾ") → its guide's name."""
    return knowledge.resolve_crop(raw_name)


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


def stage_card(crop_name: Optional[str], days: Optional[int], lang: str = "en") -> Optional[dict]:
    """Where the crop is in its life, for a progress card on the web app:
    {crop, days, total_days, stage, stage_en, from, to} — the stage name in
    `lang` when the glossary has it. None if the crop or age is unknown."""
    canonical = _resolve_crop_name(crop_name or "")
    data = _load_crop(canonical) if canonical else None
    stage = _find_stage(data, days) if data else None
    if not stage:
        return None
    from app.models.agri_glossary import stage_name
    local = stage_name(stage["name"], lang) if lang != "en" else None
    lo, hi = stage["days_range"]
    return {"crop": canonical, "days": days, "total_days": data.get("total_duration_days"),
            "stage": local or stage["name"], "stage_en": stage["name"], "from": lo, "to": hi}


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
            f"Available crops: {', '.join(knowledge.crops())}."
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
