"""Groq cloud client — free Whisper-large-v3 speech-to-text and open-weight LLMs.

Used when GROQ_API_KEY is set. It needs nothing but `requests`, so it runs on
the 512 MB Render host where local Whisper / translation models cannot fit.

Chat calls walk GROQ_LLM_MODELS in order:
  • a model this account cannot use (removed, or not on its plan) is skipped
    for the rest of the process;
  • a model that is over its rate limit is skipped for this call only, so the
    next model (with its own separate limits) answers instead.

The API key is only ever sent in the Authorization header — never logged.
"""
from __future__ import annotations

import os
import time
from typing import Optional

import requests

from app.config import GROQ_API_KEY, GROQ_API_URL, GROQ_LLM_MODELS, GROQ_STT_MODEL
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Groq's free plan accepts audio files up to 25 MB.
_MAX_AUDIO_BYTES = 24 * 1024 * 1024


class GroqError(RuntimeError):
    """A failed Groq call. `kind` is one of:
    auth · rate_limit · unavailable · too_large · bad_request · server · network
    """

    def __init__(self, kind: str, message: str, retry_after: float = 0.0) -> None:
        super().__init__(message)
        self.kind = kind
        self.retry_after = retry_after


def _reasoning_params(model: str) -> dict:
    """Keep reasoning models brief and return only their final answer."""
    m = model.lower()
    if "gpt-oss" in m:
        return {"reasoning_effort": "low", "include_reasoning": False}
    if "qwen3" in m:
        return {"reasoning_effort": "none", "reasoning_format": "hidden"}
    return {}


class GroqClient:
    def __init__(self, api_key: str = GROQ_API_KEY, base_url: str = GROQ_API_URL,
                 models: Optional[list[str]] = None, stt_model: str = GROQ_STT_MODEL,
                 timeout: float = 40.0) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.models = list(models or GROQ_LLM_MODELS)
        self.stt_model = stt_model
        self.timeout = timeout
        self.last_model: Optional[str] = None
        self._dead: set[str] = set()
        self._session = requests.Session()

    # ── HTTP ──────────────────────────────────────────────────────────────────
    def _post(self, path: str, **kwargs) -> requests.Response:
        if not self.api_key:
            raise GroqError("auth", "GROQ_API_KEY is not set")
        try:
            return self._session.post(
                self.base_url + path,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout, **kwargs,
            )
        except requests.RequestException as exc:
            raise GroqError("network", f"Groq request failed: {type(exc).__name__}") from exc

    @staticmethod
    def _raise_for(resp: requests.Response, model: str) -> None:
        if resp.status_code < 400:
            return
        try:
            err = resp.json().get("error", {}) or {}
            msg, code = str(err.get("message", "")), str(err.get("code", ""))
        except ValueError:
            msg, code = resp.text[:200], ""
        status = resp.status_code
        low = msg.lower()
        if status == 401:
            kind = "auth"
        elif status == 429:
            kind = "rate_limit"
        elif (status in (403, 404) or code in ("model_not_found", "model_decommissioned")
              or "does not exist" in low or "decommissioned" in low
              or "do not have access" in low):
            kind = "unavailable"
        elif status == 413:
            kind = "too_large"
        elif status >= 500:
            kind = "server"
        else:
            kind = "bad_request"
        try:
            retry_after = float(resp.headers.get("retry-after") or 0)
        except ValueError:
            retry_after = 0.0
        raise GroqError(kind, f"Groq {status} ({model}): {msg[:200]}", retry_after)

    # ── Chat ──────────────────────────────────────────────────────────────────
    def chat(self, messages: list[dict], *, json_mode: bool = False,
             max_tokens: int = 800, temperature: float = 0.2) -> str:
        """Reply text from the first model on the list that can answer."""
        last: Optional[GroqError] = None
        for attempt in range(2):
            waits = []
            for model in [m for m in self.models if m not in self._dead]:
                try:
                    text = self._chat_once(model, messages, json_mode, max_tokens, temperature)
                    self.last_model = model
                    return text
                except GroqError as exc:
                    last = exc
                    logger.warning("Groq chat: %s", exc)
                    if exc.kind in ("auth", "network"):
                        raise
                    if exc.kind == "unavailable":
                        self._dead.add(model)
                    elif exc.kind == "rate_limit":
                        waits.append(exc.retry_after)
            # Every model failed. If they were all just rate-limited for a few
            # seconds, wait once and try again rather than giving up.
            if attempt == 0 and last and last.kind == "rate_limit" and waits \
                    and 0 < min(waits) <= 6:
                time.sleep(min(waits))
                continue
            break
        raise last or GroqError("unavailable", "no Groq chat model is available")

    def _chat_once(self, model: str, messages: list[dict], json_mode: bool,
                   max_tokens: int, temperature: float) -> str:
        payload = {"model": model, "messages": messages, "temperature": temperature,
                   "max_completion_tokens": max_tokens, **_reasoning_params(model)}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        t0 = time.time()
        resp = self._post("/chat/completions", json=payload)
        if resp.status_code == 400 and json_mode and "json_validate_failed" in resp.text:
            # The model wrote almost-JSON; ask again without the strict check
            # and let the caller pull the object out of the text.
            payload.pop("response_format")
            resp = self._post("/chat/completions", json=payload)
        self._raise_for(resp, model)
        choice = resp.json()["choices"][0]
        content = (choice.get("message", {}).get("content") or "").strip()
        if not content:
            raise GroqError("server", f"{model} returned an empty reply "
                                      f"(finish_reason={choice.get('finish_reason')})")
        logger.info("Groq chat | %s | %.1fs | %d chars", model, time.time() - t0, len(content))
        return content

    # ── Speech-to-text ────────────────────────────────────────────────────────
    def transcribe(self, audio_path: str, language: Optional[str] = None,
                   prompt: Optional[str] = None) -> dict:
        """Whisper transcript plus the signals used to spot silence:
        {text, duration, no_speech_prob, avg_logprob}."""
        if os.path.getsize(audio_path) > _MAX_AUDIO_BYTES:
            raise GroqError("too_large", "recording is longer than the 25 MB upload limit")
        data = {"model": self.stt_model, "response_format": "verbose_json", "temperature": "0"}
        if language:
            data["language"] = language
        if prompt:
            data["prompt"] = prompt
        t0 = time.time()
        with open(audio_path, "rb") as fh:
            resp = self._post("/audio/transcriptions", data=data,
                              files={"file": (os.path.basename(audio_path) or "audio.wav", fh)})
        self._raise_for(resp, self.stt_model)
        body = resp.json()
        segments = body.get("segments") or []
        spans = [max(float(s.get("end", 0)) - float(s.get("start", 0)), 0.01) for s in segments]
        total = sum(spans) or 1.0

        def weighted(field: str, default: float) -> float:
            if not segments:
                return default
            return sum(float(s.get(field, default)) * w for s, w in zip(segments, spans)) / total

        result = {
            "text": (body.get("text") or "").strip(),
            "duration": body.get("duration"),
            "no_speech_prob": weighted("no_speech_prob", 1.0 if not body.get("text") else 0.0),
            "avg_logprob": weighted("avg_logprob", 0.0),
        }
        logger.info("Groq STT | %s | lang=%s | %.1fs | %d chars | no_speech=%.2f",
                    self.stt_model, language, time.time() - t0, len(result["text"]),
                    result["no_speech_prob"])
        return result


_client: Optional[GroqClient] = None


def get_groq_client() -> GroqClient:
    global _client
    if _client is None:
        _client = GroqClient()
    return _client


def set_groq_client(client: Optional[GroqClient]) -> None:
    """Swap the shared client (tests use a fake one)."""
    global _client
    _client = client
