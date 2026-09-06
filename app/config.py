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
LLM_MODEL_ID: str = os.getenv("LLM_MODEL_ID", "meta-llama/Llama-3.1-8B-Instruct")

# ─── Embeddings ───────────────────────────────────────────────────────────────
EMBEDDING_MODEL_ID: str = os.getenv("EMBEDDING_MODEL_ID", "BAAI/bge-m3")

# ─── TTS (Indic) ──────────────────────────────────────────────────────────────
TTS_MODEL_ID: str = os.getenv("TTS_MODEL_ID", "ai4bharat/indic-parler-tts")

# ─── Hugging Face ─────────────────────────────────────────────────────────────
HF_TOKEN: str = os.getenv("HF_TOKEN", "")
# Set true to call HF Inference API instead of loading models locally (for CPU dev)
USE_HF_INFERENCE_API: bool = os.getenv("USE_HF_INFERENCE_API", "true").lower() == "true"
# Set true to skip loading IndicTrans2 and return stub translations (for fast local dev)
USE_STUB_TRANSLATION: bool = os.getenv("USE_STUB_TRANSLATION", "false").lower() == "true"
# Set true to skip HF API calls and use StubLLM (for dev without HF token)
USE_STUB_LLM: bool = os.getenv("USE_STUB_LLM", "false").lower() == "true"

# ─── Weather API ──────────────────────────────────────────────────────────────
WEATHER_API_URL: str = os.getenv("WEATHER_API_URL", "https://api.open-meteo.com/v1/forecast")
GEOCODING_API_URL: str = os.getenv(
    "GEOCODING_API_URL", "https://geocoding-api.open-meteo.com/v1/search"
)

# ─── RAG ──────────────────────────────────────────────────────────────────────
TOP_K: int = int(os.getenv("TOP_K", "5"))
CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "150"))

# ─── LLM Generation ───────────────────────────────────────────────────────────
MAX_NEW_TOKENS: int = int(os.getenv("MAX_NEW_TOKENS", "512"))
TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.3"))

# ─── App ──────────────────────────────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
DEV_MODE: bool = os.getenv("DEV_MODE", "true").lower() == "true"

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
