"""Web app and JSON API.

    GET  /                the farmer-facing web app (app/web/static)
    GET  /api/config      languages, every on-screen message in 4 languages,
                          sample questions and crop names
    POST /api/ask         a typed question             → the answer, as JSON
    POST /api/voice       a recorded question (audio)  → the answer, as JSON
    POST /api/speak       {text, lang}                 → the answer read aloud (MP3)
    GET  /api/health      liveness, and which engines are switched on
    GET  /api/docs        interactive API docs
         /classic         the original Gradio screen, on the same pipeline

The question pipeline is app.ui.gradio_app._pipeline_iter — shared with the
Gradio screen, so both always answer the same way. The server is stateless:
a question that was asked back about ("how many days old?") travels to the
browser as `pending` and comes back with the farmer's reply.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from app.config import DEV_MODE, REGIONAL_READY, VOICE_READY
from app.ui.i18n import (
    CROP_NAMES, DEFAULT_LANG, LANG_CHOICES, LANG_CODES, LANG_NAMES, STRINGS, normalize_lang, t,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)

STATIC = Path(__file__).resolve().parent / "static"

# Browsers record in different containers: webm (Chrome, Android), mp4 (Safari),
# ogg (Firefox). Whisper on Groq tells them apart by the file extension.
_AUDIO_SUFFIX = {
    "audio/webm": ".webm", "video/webm": ".webm", "audio/ogg": ".ogg",
    "audio/mp4": ".m4a", "audio/x-m4a": ".m4a", "audio/aac": ".m4a",
    "audio/mpeg": ".mp3", "audio/wav": ".wav", "audio/x-wav": ".wav", "audio/wave": ".wav",
}
_MAX_AUDIO_BYTES = 10 * 1024 * 1024   # ~10 minutes of compressed speech
_MAX_QUESTION = 600                   # characters
_MAX_SPOKEN = 1500                    # characters read aloud
_MAX_PENDING = 8 * 1024               # bytes of a remembered question

# A few questions at a time is plenty for one small server, and it keeps a
# burst of farmers from exhausting the free speech / LLM quota in seconds.
_PIPELINE_SLOTS = threading.BoundedSemaphore(4)


class _RateLimit:
    """At most `per_minute` requests per client per minute (sliding window)."""

    def __init__(self, per_minute: int) -> None:
        self.per_minute = per_minute
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, client: str) -> bool:
        now = time.time()
        with self._lock:
            if len(self._hits) > 10_000:      # forget long-gone visitors
                self._hits.clear()
            hits = self._hits[client]
            while hits and now - hits[0] > 60:
                hits.popleft()
            if len(hits) >= self.per_minute:
                return False
            hits.append(now)
            return True


_ask_limit = _RateLimit(20)
_speak_limit = _RateLimit(40)


def _client(request: Request) -> str:
    # Render (and most hosts) put the visitor's address first in X-Forwarded-For.
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "?")


def _too_many(lang: str) -> JSONResponse:
    return JSONResponse({"error": t("err_busy", lang)}, status_code=429)


# ── Requests ──────────────────────────────────────────────────────────────────

class AskRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=_MAX_QUESTION)
    lang: str = DEFAULT_LANG
    location: str = Field("", max_length=120)
    pending: Optional[dict] = None


class SpeakRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=_MAX_SPOKEN * 2)
    lang: str = DEFAULT_LANG


def _clean_pending(pending) -> Optional[dict]:
    """The question the farmer was asked about, as sent back by the browser.
    Anything malformed is dropped — the reply is then read as a new question."""
    if not isinstance(pending, dict) or not isinstance(pending.get("missing"), list):
        return None
    if len(json.dumps(pending, ensure_ascii=False)) > _MAX_PENDING:
        return None
    return pending


# ── The answer ────────────────────────────────────────────────────────────────

def _answer(audio_path: Optional[str], text: str, location: str, lang: str,
            pending: Optional[dict]) -> dict:
    """Run the shared pipeline to the words (the voice is fetched separately
    from /api/speak, so the farmer reads the answer while it is spoken)."""
    from app.ui.gradio_app import _pipeline_iter

    started = time.time()
    with _PIPELINE_SLOTS:
        result = None
        for result in _pipeline_iter(audio_path, text, location, lang, pending, speak=False):
            pass
    q_lang, mode = result["detected_key"] or (lang, "voice" if audio_path else "typed")
    flags = result["tools_flags"] or (False, False, False)
    pend = result["pending"]
    speech_text, speech_lang = result.get("speech") or (result["answer"], lang)
    return {
        "answer": result["answer"],
        "heard": result["heard"] or "",
        "mode": mode,
        "question_lang": q_lang,
        "speech": {"text": speech_text, "lang": speech_lang},
        "pending": pend,
        "missing": (pend or {}).get("missing", []),
        "tools": dict(zip(("crop", "weather", "scheme"), map(bool, flags))),
        "cards": result.get("cards") or {},
        "english": result["english"] or "",
        "understood": result["intent"] or "",
        "trace": result["trace"] if DEV_MODE else "",
        "ms": int((time.time() - started) * 1000),
    }


def _config() -> dict:
    from app.ui.gradio_app import _examples, _mode_info
    return {
        "languages": [{"code": code, "label": label} for label, code in LANG_CHOICES],
        "default": DEFAULT_LANG,
        "strings": {lang: {key: entry.get(lang) or entry[DEFAULT_LANG]
                           for key, entry in STRINGS.items()}
                    for lang in LANG_CODES},
        "lang_names": LANG_NAMES,
        "examples": {lang: _examples(lang) for lang in LANG_CODES},
        "crops": CROP_NAMES,
        "voice": VOICE_READY,
        "regional": REGIONAL_READY,
        "mode": _mode_info(),
        "dev": DEV_MODE,
    }


# ── App ───────────────────────────────────────────────────────────────────────

def create_app(with_classic: bool = True) -> FastAPI:
    app = FastAPI(title="Agri Assistant API",
                  description="Voice-first farm advice in English, Hindi, Punjabi and Marathi.",
                  version="2.0", docs_url="/api/docs", redoc_url=None)
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    def page(name: str, media_type: Optional[str] = None) -> FileResponse:
        # The shell must never be stale after a deploy; the service worker
        # handles offline use.
        return FileResponse(STATIC / name, media_type=media_type,
                            headers={"Cache-Control": "no-cache"})

    @app.get("/", include_in_schema=False)
    def index():
        return page("index.html")

    @app.get("/sw.js", include_in_schema=False)
    def service_worker():
        return page("sw.js", "application/javascript")

    @app.get("/manifest.webmanifest", include_in_schema=False)
    def manifest():
        return page("manifest.webmanifest", "application/manifest+json")

    @app.get("/api/health")
    def health():
        from app.ui.gradio_app import _mode_info
        return {"status": "ok", "mode": _mode_info(), "voice": VOICE_READY,
                "languages": list(LANG_CODES)}

    @app.get("/api/config")
    def config():
        return JSONResponse(_config(), headers={"Cache-Control": "public, max-age=300"})

    @app.post("/api/ask")
    def ask(req: AskRequest, request: Request):
        lang = normalize_lang(req.lang)
        if not _ask_limit.allow(_client(request)):
            return _too_many(lang)
        try:
            return _answer(None, req.text.strip(), req.location.strip(), lang,
                           _clean_pending(req.pending))
        except Exception as exc:
            logger.exception("ask failed: %s", exc)
            return JSONResponse({"error": t("web_error", lang)}, status_code=500)

    @app.post("/api/voice")
    async def voice(request: Request, audio: UploadFile = File(...),
                    lang: str = Form(DEFAULT_LANG), location: str = Form(""),
                    pending: str = Form("")):
        lang = normalize_lang(lang)
        if not VOICE_READY:
            raise HTTPException(400, t("err_no_input_lite", lang))
        if not _ask_limit.allow(_client(request)):
            return _too_many(lang)
        data = await audio.read()
        if not data:
            raise HTTPException(400, t("err_no_speech", lang))
        if len(data) > _MAX_AUDIO_BYTES:
            raise HTTPException(413, t("err_too_long", lang))
        kind = (audio.content_type or "").split(";")[0].strip().lower()
        suffix = _AUDIO_SUFFIX.get(kind) or Path(audio.filename or "").suffix or ".webm"
        try:
            pending_dict = _clean_pending(json.loads(pending)) if pending else None
        except ValueError:
            pending_dict = None
        fd, path = tempfile.mkstemp(prefix="question-", suffix=suffix)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            from starlette.concurrency import run_in_threadpool
            return await run_in_threadpool(_answer, path, "", location.strip()[:120], lang,
                                           pending_dict)
        except Exception as exc:
            logger.exception("voice failed: %s", exc)
            return JSONResponse({"error": t("web_error", lang)}, status_code=500)
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

    @app.post("/api/speak")
    def speak(req: SpeakRequest, request: Request):
        lang = normalize_lang(req.lang)
        if not _speak_limit.allow(_client(request)):
            return _too_many(lang)
        from app.ui.gradio_app import _speak
        path = _speak(req.text[:_MAX_SPOKEN * 2], lang, [])
        if not path or not os.path.exists(path):
            raise HTTPException(503, t("err_service", lang))
        media = "audio/wav" if path.endswith(".wav") else "audio/mpeg"
        return FileResponse(path, media_type=media, headers={"Cache-Control": "no-store"},
                            background=BackgroundTask(_remove, path))

    if with_classic:
        import gradio as gr
        from app.ui.gradio_app import _CSS, _HEAD, build_theme, build_ui
        app = gr.mount_gradio_app(app, build_ui(), path="/classic",
                                  theme=build_theme(), css=_CSS, head=_HEAD)
    return app


def _remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass
