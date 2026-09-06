"""LLM provider abstraction (Phase 4).

The LLM always receives and returns English text.
Regional language handling is done by IndicTrans2 at the pipeline boundaries.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod

from app.config import LLM_MODEL_ID, MAX_NEW_TOKENS, TEMPERATURE, HF_TOKEN, USE_HF_INFERENCE_API, USE_STUB_LLM
from app.utils.logging import get_logger

logger = get_logger(__name__)


class BaseLLM(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Generate a response for the given English prompt."""


class HuggingFaceLocalLLM(BaseLLM):
    """Loads the model locally via transformers (Phase 4 – GPU required)."""

    def __init__(self, model_id: str = LLM_MODEL_ID, device: str = "cpu") -> None:
        self.model_id = model_id
        self.device = device
        self._pipeline = None

    def _load(self) -> None:
        if self._pipeline is not None:
            return
        logger.info("Loading LLM: %s on %s", self.model_id, self.device)
        raise NotImplementedError("HuggingFaceLocalLLM will be implemented in Phase 4.")

    def generate(self, prompt: str) -> str:
        self._load()
        raise NotImplementedError("HuggingFaceLocalLLM will be implemented in Phase 4.")


class HuggingFaceInferenceAPILLM(BaseLLM):
    """
    Calls the HF Inference API – no local GPU needed.
    Used during local development (USE_HF_INFERENCE_API=true).
    """

    def __init__(self, model_id: str = LLM_MODEL_ID, token: str = HF_TOKEN) -> None:
        self.model_id = model_id
        self.token = token

    def generate(self, prompt: str) -> str:
        import requests

        t0 = time.time()
        api_url = f"https://api-inference.huggingface.co/models/{self.model_id}"
        headers = {"Authorization": f"Bearer {self.token}"}
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": MAX_NEW_TOKENS,
                "temperature": TEMPERATURE,
                "return_full_text": False,
            },
        }
        resp = requests.post(api_url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        result = resp.json()
        text = result[0]["generated_text"] if isinstance(result, list) else str(result)
        logger.info("HF Inference API LLM | %.2fs", time.time() - t0)
        return text.strip()


class StubLLM(BaseLLM):
    """Returns context-aware responses for local dev without an HF token."""

    def generate(self, prompt: str) -> str:
        import re

        logger.warning("StubLLM: building response from injected context.")

        # ── Intent extraction ────────────────────────────────────────────────
        if '"intent"' in prompt:
            # Try to detect crop from the query
            query = ""
            m = re.search(r"Query:\s*(.+)", prompt)
            if m:
                query = m.group(1).lower()

            crop = "wheat"
            for c in ["onion", "rice", "tomato", "cotton", "maize", "corn", "paddy"]:
                if c in query:
                    crop = c
                    break

            days_match = re.search(r"(\d+)\s*day", query)
            days = int(days_match.group(1)) if days_match else 40

            needs_weather = any(w in query for w in ["rain", "weather", "temperature", "forecast", "flood", "drought"])
            needs_scheme = any(w in query for w in ["scheme", "subsidy", "government", "loan", "insurance"])

            return (
                f'{{"intent": "crop_advice", "crop": "{crop}", "crop_stage_days": {days}, '
                f'"location": null, "needs_weather": {str(needs_weather).lower()}, '
                f'"needs_scheme": {str(needs_scheme).lower()}, "needs_crop_info": true}}'
            )

        # ── Final answer — extract key facts from injected crop context ──────
        # Pull crop name and current stage from the crop knowledge section
        crop_name = "your crop"
        stage_name = ""
        irrigation = ""
        fertilizer = ""
        watch_for = ""
        tips = ""

        m = re.search(r"Crop\s+:\s+(.+)", prompt)
        if m:
            crop_name = m.group(1).strip()

        m = re.search(r"=== Current Stage:\s*(.+?)\s*===", prompt)
        if m:
            stage_name = m.group(1).strip()

        m = re.search(r"Irrigation\s+:\s+(.+)", prompt)
        if m:
            irrigation = m.group(1).strip()

        m = re.search(r"Fertilizer\s+:\s+(.+)", prompt)
        if m:
            fertilizer = m.group(1).strip()

        m = re.search(r"Watch for\s+:\s+(.+)", prompt)
        if m:
            watch_for = m.group(1).strip()

        m = re.search(r"Tips\s+:\s+(.+)", prompt)
        if m:
            tips = m.group(1).strip()

        # Also pull the farmer's question
        farmer_q = ""
        m = re.search(r"Farmer's Question \(English\):\s*(.+)", prompt)
        if m:
            farmer_q = m.group(1).strip()

        stage_line = f" — currently in **{stage_name}** stage" if stage_name else ""
        answer_lines = [
            f"Situation:",
            f"Your {crop_name} crop{stage_line}. Based on crop knowledge for this stage:\n",
            "What you should do:",
        ]
        step = 1
        if irrigation:
            answer_lines.append(f"{step}. Irrigation: {irrigation}")
            step += 1
        if fertilizer:
            answer_lines.append(f"{step}. Fertilizer: {fertilizer}")
            step += 1
        if watch_for:
            answer_lines.append(f"{step}. Watch for: {watch_for}")
            step += 1
        if tips:
            answer_lines.append(f"{step}. Tips: {tips}")

        answer_lines += [
            "",
            "Important:",
            "This response is generated from the crop knowledge base. "
            "Consult your local KVK for location-specific advice.",
        ]
        return "\n".join(answer_lines)


def get_llm(device: str = "cpu", use_stub: bool = False) -> BaseLLM:
    if use_stub or USE_STUB_LLM:
        return StubLLM()
    if USE_HF_INFERENCE_API:
        return HuggingFaceInferenceAPILLM()
    return HuggingFaceLocalLLM(device=device)
