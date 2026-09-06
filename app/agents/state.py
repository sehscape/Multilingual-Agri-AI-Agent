"""Shared state / context object passed through the agent pipeline.

Architecture:  Regional speech → STT → original_text
               → IndicTrans2 → english_text
               → Agent/Tools → english_answer
               → IndicTrans2 → regional_answer
               → Indic TTS → audio
"""
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class AgentState:
    # ── Input boundary (regional language) ────────────────────────────────────
    source_language: str = "hi"          # ISO 639-1 code: "hi" | "mr" | "pa"
    original_text: str = ""              # Raw STT output in regional language
    english_text: str = ""               # IndicTrans2 → English

    # ── Intent / query understanding (English, internal) ──────────────────────
    intent: str = "unknown"
    crop: Optional[str] = None
    crop_stage_days: Optional[int] = None
    location: Optional[str] = None
    needs_weather: bool = False
    needs_scheme: bool = False
    needs_crop_info: bool = False

    # ── Tool outputs (all in English) ─────────────────────────────────────────
    weather_data: Optional[dict] = None
    crop_data: Optional[dict] = None
    scheme_docs: List[dict] = field(default_factory=list)

    # ── Output boundary ───────────────────────────────────────────────────────
    english_answer: str = ""             # LLM answer in English
    regional_answer: str = ""            # IndicTrans2 English → regional language
    sources: List[str] = field(default_factory=list)

    # ── Observability ─────────────────────────────────────────────────────────
    latency: dict = field(default_factory=dict)   # component → seconds
    trace: List[str] = field(default_factory=list)

    def add_trace(self, msg: str) -> None:
        self.trace.append(msg)

    def trace_summary(self) -> str:
        return "\n".join(self.trace)
