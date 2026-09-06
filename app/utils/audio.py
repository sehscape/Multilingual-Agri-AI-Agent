"""Audio utilities: ffmpeg discovery and format conversion.

Browsers record in webm/opus. Whisper needs WAV at 16 kHz mono.
We call ffmpeg directly via subprocess using the absolute path,
so we never depend on ffmpeg being in the system PATH.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.utils.logging import get_logger

logger = get_logger(__name__)

# ─── Known ffmpeg install locations on Windows ────────────────────────────────
_FFMPEG_SEARCH_DIRS = [
    # winget / Gyan.FFmpeg
    Path.home() / "AppData/Local/Microsoft/WinGet/Packages",
    # chocolatey
    Path("C:/ProgramData/chocolatey/bin"),
    # manual installs
    Path("C:/ffmpeg/bin"),
    Path("C:/Program Files/ffmpeg/bin"),
]


def find_ffmpeg() -> str | None:
    """Return the absolute path to ffmpeg.exe, or None if not found."""
    # 1. Already on PATH
    on_path = shutil.which("ffmpeg")
    if on_path:
        return on_path

    # 2. Search known install directories recursively
    for base in _FFMPEG_SEARCH_DIRS:
        if not base.exists():
            continue
        for exe in base.rglob("ffmpeg.exe"):
            return str(exe)

    return None


def ensure_wav(audio_path: str) -> str:
    """
    Convert any audio file to 16 kHz mono WAV using ffmpeg directly.
    Always resamples — even existing WAV files may be at 44100 Hz
    (e.g. Gradio saves microphone recordings as WAV at the browser's
    native sample rate, not 16 kHz).
    Returns the original path if ffmpeg is unavailable.
    """
    ffmpeg_exe = find_ffmpeg()
    if not ffmpeg_exe:
        logger.warning("ffmpeg not found — passing original audio to Whisper as-is.")
        return audio_path

    tmp_wav = tempfile.mktemp(suffix=".wav")
    cmd = [
        ffmpeg_exe,
        "-y",            # overwrite output
        "-i", audio_path,
        "-ar", "16000",  # 16 kHz
        "-ac", "1",      # mono
        "-f", "wav",
        tmp_wav,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        if result.returncode == 0:
            logger.info("Audio converted to WAV: %s → %s", audio_path, tmp_wav)
            return tmp_wav
        else:
            err = result.stderr.decode(errors="ignore").strip().splitlines()[-1]
            logger.warning("ffmpeg conversion failed: %s — using original.", err)
            return audio_path
    except Exception as exc:
        logger.warning("ffmpeg error: %s — using original.", exc)
        return audio_path
