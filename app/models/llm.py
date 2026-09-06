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
    """Returns canned responses for local dev without an HF token."""

    def generate(self, prompt: str) -> str:
        logger.warning("StubLLM: returning placeholder response.")
        # Intent extraction prompts contain the JSON schema — return valid JSON
        if '"intent"' in prompt:
            return (
                '{"intent": "crop_advice", "crop": "wheat", "crop_stage_days": 40, '
                '"location": null, "needs_weather": true, "needs_scheme": false, '
                '"needs_crop_info": true}'
            )
        # Final answer prompt
        return (
            "Situation:\n"
            "Your wheat crop is 40 days old and rain is expected in the next few days.\n\n"
            "What you should do:\n"
            "1. Avoid additional irrigation for the next 3 days.\n"
            "2. Ensure proper drainage channels are clear to prevent waterlogging.\n"
            "3. Monitor for fungal diseases (powdery mildew, rust) after the rain.\n"
            "4. Do not apply fertilizer immediately before heavy rain — it will wash away.\n\n"
            "Important:\n"
            "This is general guidance. Consult your local KVK for crop-specific advice."
        )


def get_llm(device: str = "cpu", use_stub: bool = False) -> BaseLLM:
    if use_stub or USE_STUB_LLM:
        return StubLLM()
    if USE_HF_INFERENCE_API:
        return HuggingFaceInferenceAPILLM()
    return HuggingFaceLocalLLM(device=device)
