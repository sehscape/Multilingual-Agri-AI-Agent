"""Central configuration – all values come from environment variables."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
VECTORSTORE_PATH = DATA_DIR / os.getenv("VECTORSTORE_PATH", "data/vectorstore").split("/")[-1]
SCHEMES_RAW_DIR = DATA_DIR / "schemes" / "raw"
SCHEMES_PROCESSED_DIR = DATA_DIR / "schemes" / "processed"
CROPS_DIR = DATA_DIR / "crops"

# ─── STT ──────────────────────────────────────────────────────────────────────
WHISPER_MODEL_ID: str = os.getenv("WHISPER_MODEL_ID", "openai/whisper-large-v3")

# ─── Translation (IndicTrans2) ─────────────────────────────────────────────────
# Two separate checkpoints: one per direction
TRANSLATION_MODEL_INDIC_EN: str = os.getenv(
    "TRANSLATION_MODEL_INDIC_EN", "ai4bharat/indictrans2-indic-en-1B"
)
TRANSLATION_MODEL_EN_INDIC: str = os.getenv(
    "TRANSLATION_MODEL_EN_INDIC", "ai4bharat/indictrans2-en-indic-1B"
)

# IndicTrans2 uses Flores-200 language codes
INDICTRANS2_LANG_CODES: dict[str, str] = {
    "hi": "hin_Deva",   # Hindi  – Devanagari
    "mr": "mar_Deva",   # Marathi – Devanagari
    "pa": "pan_Guru",   # Punjabi – Gurmukhi
    "en": "eng_Latn",   # English – Latin
}

# ─── LLM ──────────────────────────────────────────────────────────────────────
# Production model (GPU / HF Inference API) — the full-size open model.
LLM_MODEL_ID: str = os.getenv("LLM_MODEL_ID", "meta-llama/Llama-3.1-8B-Instruct")
# Small open-source model that runs locally on CPU (no GPU). Used by
# HuggingFaceLocalLLM. Qwen2.5-0.5B-Instruct is ungated, ~1GB, Apache-2.0.
# Bump to Qwen/Qwen2.5-1.5B-Instruct for better quality if the machine allows.
LOCAL_LLM_MODEL_ID: str = os.getenv("LOCAL_LLM_MODEL_ID", "Qwen/Qwen2.5-0.5B-Instruct")

# ─── Embeddings ───────────────────────────────────────────────────────────────
EMBEDDING_MODEL_ID: str = os.getenv("EMBEDDING_MODEL_ID", "BAAI/bge-m3")

# ─── TTS (Indic) ──────────────────────────────────────────────────────────────
TTS_MODEL_ID: str = os.getenv("TTS_MODEL_ID", "ai4bharat/indic-parler-tts")
# Which TTS engine to use for voice output:
#   "gtts"   → lightweight, CPU-friendly, needs internet (good for local dev)
#   "parler" → ai4bharat/indic-parler-tts (production quality, large, GPU)
#   "stub"   → no audio (text answer only)
TTS_ENGINE: str = os.getenv("TTS_ENGINE", "gtts")

# ─── Hugging Face ─────────────────────────────────────────────────────────────
HF_TOKEN: str = os.getenv("HF_TOKEN", "")
# Set true to call HF Inference API instead of loading models locally (for CPU dev)
USE_HF_INFERENCE_API: bool = os.getenv("USE_HF_INFERENCE_API", "true").lower() == "true"
# Set true to skip loading IndicTrans2 and return stub translations (for fast local dev)
USE_STUB_TRANSLATION: bool = os.getenv("USE_STUB_TRANSLATION", "false").lower() == "true"
# Set true to skip HF API calls and use StubLLM (for dev without HF token)
USE_STUB_LLM: bool = os.getenv("USE_STUB_LLM", "false").lower() == "true"
# Set true to skip FAISS index load and return stub scheme responses (for fast local dev)
USE_STUB_RAG: bool = os.getenv("USE_STUB_RAG", "false").lower() == "true"

# ─── Weather API ──────────────────────────────────────────────────────────────
WEATHER_API_URL: str = os.getenv("WEATHER_API_URL", "https://api.open-meteo.com/v1/forecast")
GEOCODING_API_URL: str = os.getenv(
    "GEOCODING_API_URL", "https://geocoding-api.open-meteo.com/v1/search"
)

# ─── RAG ──────────────────────────────────────────────────────────────────────
TOP_K: int = int(os.getenv("TOP_K", "5"))
CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "150"))
# Minimum cosine relevance (0–1) a retrieved chunk must reach to be trusted.
# Chunks below this are dropped; if none qualify the tool reports "insufficient
# information" instead of presenting weak matches as fact (see spec §12).
RAG_MIN_SCORE: float = float(os.getenv("RAG_MIN_SCORE", "0.30"))
# Retrieval backend for the scheme tool:
#   "faiss" → semantic search with sentence-transformers embeddings (default)
#   "bm25"  → pure-Python keyword search, no heavy deps (used in LITE_MODE)
RAG_BACKEND: str = os.getenv("RAG_BACKEND", "faiss").lower()
# Absolute BM25 score the top hit must reach for the bm25 backend to trust the
# result (keyword scores are not 0-1). Below this → "insufficient information".
BM25_MIN_SCORE: float = float(os.getenv("BM25_MIN_SCORE", "2.0"))

# ─── Agent engine ─────────────────────────────────────────────────────────────
#   "langchain"  → LangChain ReAct AgentExecutor with tool-calling (default)
#   "sequential" → deterministic orchestrator (intent flags → tools in order)
# If LangChain isn't installed the app falls back to "sequential" automatically.
AGENT_BACKEND: str = os.getenv("AGENT_BACKEND", "langchain").lower()

# ─── LLM Generation ───────────────────────────────────────────────────────────
MAX_NEW_TOKENS: int = int(os.getenv("MAX_NEW_TOKENS", "512"))
TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.3"))

# ─── App ──────────────────────────────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
DEV_MODE: bool = os.getenv("DEV_MODE", "true").lower() == "true"

# ─── LITE mode (small free hosts: Render free tier, 512 MB RAM) ────────────────
# Turns off every heavy component so the app fits in ~350 MB:
#   • no microphone / Whisper  (typed input only)
#   • keyword scheme search    (RAG_BACKEND=bm25, no torch)
#   • rule-based answers        (USE_STUB_LLM)
#   • English voice out         (USE_STUB_TRANSLATION, gTTS)
LITE_MODE: bool = os.getenv("LITE_MODE", "false").lower() == "true"
if LITE_MODE:
    RAG_BACKEND = "bm25"
    USE_STUB_LLM = True
    USE_STUB_TRANSLATION = True
    USE_STUB_RAG = False
    TTS_ENGINE = "gtts"
    DEV_MODE = False

# Human-readable language names keyed by ISO 639-1 code used in the UI
SUPPORTED_LANGUAGES: dict[str, str] = {
    "hi": "Hindi",
    "mr": "Marathi",
    "pa": "Punjabi",
}

# Valid agent intents
AGENT_INTENTS = [
    "crop_advice",
    "weather",
    "government_scheme",
    "irrigation",
    "fertilizer",
    "pest_or_disease",
    "general_farming",
    "multiple",
    "unknown",
]
