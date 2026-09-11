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

# ─── Groq cloud: free speech-to-text + open-weight LLM ────────────────────────
# With a free key from console.groq.com the app hears and answers in Hindi,
# Punjabi and Marathi even on a 512 MB host: Whisper-large-v3 turns speech into
# text, and an open-weight LLM understands the question and writes the answer
# in the farmer's language (from the tool results only). Keep the key in .env
# or the host's environment settings — never in the repo.
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "").strip()
GROQ_API_URL: str = os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1")
# Tried in order. A model this account can't use is skipped for good; one that
# is over its rate limit is skipped for that request only.
GROQ_LLM_MODELS: list[str] = [
    m.strip() for m in os.getenv(
        "GROQ_LLM_MODELS",
        "openai/gpt-oss-120b,openai/gpt-oss-20b,llama-3.3-70b-versatile",
    ).split(",") if m.strip()
]
GROQ_STT_MODEL: str = os.getenv("GROQ_STT_MODEL", "whisper-large-v3")
USE_GROQ: bool = bool(GROQ_API_KEY) and os.getenv("USE_GROQ", "true").lower() == "true"

# Which speech-to-text engine hears the microphone:
#   auto  → Groq Whisper when GROQ_API_KEY is set, else local Whisper (full build)
#   groq  → Groq Whisper only        local → local Whisper only
STT_BACKEND: str = os.getenv("STT_BACKEND", "auto").lower()

# ─── LITE mode (small free hosts: Render free tier, 512 MB RAM) ────────────────
# Turns off every heavy component so the app fits in ~350 MB:
#   • no local Whisper          (voice needs GROQ_API_KEY)
#   • keyword scheme search    (RAG_BACKEND=bm25, no torch)
#   • rule-based agent brain    (USE_STUB_LLM)
#   • no local translator       (USE_STUB_TRANSLATION; Groq writes regional answers)
LITE_MODE: bool = os.getenv("LITE_MODE", "false").lower() == "true"
if LITE_MODE:
    RAG_BACKEND = "bm25"
    USE_STUB_LLM = True
    USE_STUB_TRANSLATION = True
    USE_STUB_RAG = False
    TTS_ENGINE = "gtts"
    DEV_MODE = False

# ─── Resolved capabilities (what this build can actually do) ───────────────────
if STT_BACKEND == "groq" or (STT_BACKEND == "auto" and USE_GROQ):
    STT_ENGINE = "groq" if USE_GROQ else "none"
elif not LITE_MODE:
    STT_ENGINE = "local"          # transformers Whisper on this machine
else:
    STT_ENGINE = "none"
VOICE_READY: bool = STT_ENGINE != "none"
# Questions and answers in Hindi / Punjabi / Marathi: Groq LLM, or IndicTrans2.
REGIONAL_READY: bool = USE_GROQ or not USE_STUB_TRANSLATION

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
