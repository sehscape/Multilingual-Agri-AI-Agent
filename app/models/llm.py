"""LLM provider abstraction (Phase 4).

The LLM always receives and returns English text.
Regional language handling is done by IndicTrans2 at the pipeline boundaries.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod

from app.config import LLM_MODEL_ID, MAX_NEW_TOKENS, TEMPERATURE, HF_TOKEN, USE_HF_INFERENCE_API
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
    """Returns a canned English response for unit tests."""

    def generate(self, prompt: str) -> str:
        logger.warning("StubLLM: returning placeholder response.")
        return (
            "Situation:\nYour onion crop is 45 days old and heavy rain is expected.\n\n"
            "What you should do:\n"
            "1. Avoid additional irrigation for the next 3 days.\n"
            "2. Ensure proper drainage channels are clear.\n"
            "3. Monitor for fungal disease after the rain.\n\n"
            "Important:\nThis is general guidance. Consult your local KVK for specific advice."
        )


def get_llm(device: str = "cpu", use_stub: bool = False) -> BaseLLM:
    if use_stub:
        return StubLLM()
    if USE_HF_INFERENCE_API:
        return HuggingFaceInferenceAPILLM()
    return HuggingFaceLocalLLM(device=device)
