<div align="center">

# 🌾 Farmer Advisory Voice Agent

### A multilingual AI assistant that speaks to Indian farmers in their own language

[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)](https://python.org)
[![Gradio](https://img.shields.io/badge/Gradio-4.x-orange?logo=gradio)](https://gradio.app)
[![HuggingFace](https://img.shields.io/badge/HuggingFace-Spaces-yellow?logo=huggingface)](https://huggingface.co)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

*Farmer speaks in Hindi, Marathi, or Punjabi → AI responds with crop advice, weather, and government scheme information — in their own language, as voice output.*

</div>

---

## The Problem

India has 140+ million farming households. Most farmers speak only their regional language, cannot read complex government documents, and have no easy way to get reliable, personalized agricultural advice — especially in rural areas with limited connectivity or literacy.

**This project builds a voice-first AI assistant that bridges that gap.**

---

## What It Does

A farmer picks up their phone, speaks naturally in Hindi, Marathi, or Punjabi, and asks something like:

> *"मेरी गेहूं 40 दिन की है, क्या खाद डालूं?"*
> *(My wheat is 40 days old, what fertilizer should I apply?)*

The agent:
1. **Transcribes** the speech using Whisper (auto-detects language)
2. **Translates** to English using IndicTrans2
3. **Understands intent** — crop, stage, needs weather / scheme info
4. **Calls tools** — crop knowledge base, live weather forecast, government scheme documents
5. **Generates a practical answer** in English using an LLM
6. **Translates back** to the farmer's language
7. **Speaks the answer** using Indic TTS

The farmer hears actionable advice in their own language.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     FARMER'S PHONE                          │
│                  🎙️ Speaks regional language                 │
└──────────────────────────┬──────────────────────────────────┘
                           │ Audio
                           ▼
                   ┌───────────────┐
                   │  Whisper STT  │  ← Auto language detection
                   │  (tiny/large) │    Hi / Mr / Pa
                   └───────┬───────┘
                           │ Regional text
                           ▼
                   ┌───────────────┐
                   │  IndicTrans2  │  ← Regional → English
                   │  indic-en-1B  │
                   └───────┬───────┘
                           │ English text
                           ▼
          ┌────────────────────────────────┐
          │        LLM Agent (English)     │
          │   Intent extraction + Routing  │
          └────┬──────────┬───────────┬───┘
               │          │           │
               ▼          ▼           ▼
        ┌──────────┐ ┌─────────┐ ┌──────────┐
        │  Crop    │ │ Weather │ │ Scheme   │
        │ Knowledge│ │  Tool   │ │ RAG Tool │
        │ (JSON DB)│ │Open-Met.│ │ (FAISS)  │
        └──────────┘ └─────────┘ └──────────┘
               │          │           │
               └──────────┴───────────┘
                           │ Tool outputs
                           ▼
                   ┌───────────────┐
                   │   LLM Answer  │  ← Practical, structured
                   │  Generation   │    farming advice
                   └───────┬───────┘
                           │ English answer
                           ▼
                   ┌───────────────┐
                   │  IndicTrans2  │  ← English → Regional
                   │  en-indic-1B  │
                   └───────┬───────┘
                           │ Regional text
                           ▼
                   ┌───────────────┐
                   │   Indic TTS   │  ← Text → Speech
                   │ (ai4bharat)   │
                   └───────┬───────┘
                           │ Audio
                           ▼
                  🔊 Farmer hears the answer
                     in their own language
```

> **Key design principle:** All AI reasoning happens in English. Regional language appears only at the input (STT) and output (TTS) boundaries. This avoids multilingual hallucination and keeps the LLM focused.

---

## Features

| Feature | Details |
|---|---|
| **Languages** | Hindi, Marathi, Punjabi (auto-detected) |
| **Crop Knowledge** | Wheat, Rice, Onion, Tomato, Cotton, Maize — stage-specific advice |
| **Live Weather** | Real forecast via Open-Meteo API — temperature, rain, wind + farming advisories |
| **Govt Schemes** | PM-KISAN, PMFBY crop insurance, Kisan Credit Card, Soil Health Card |
| **Voice I/O** | Whisper STT + Indic Parler TTS |
| **No API Key Needed** | Weather API is free and open |
| **Gradio UI** | Clean browser interface, microphone input, voice output |

---

## Tech Stack

| Component | Technology |
|---|---|
| UI | [Gradio](https://gradio.app) |
| Speech-to-Text | [OpenAI Whisper](https://github.com/openai/whisper) |
| Translation | [IndicTrans2](https://github.com/AI4Bharat/IndicTrans2) (AI4Bharat) |
| LLM | [Llama 3.1 8B](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct) via HF Inference API |
| Embeddings | [paraphrase-multilingual-MiniLM](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2) (dev) / [BGE-M3](https://huggingface.co/BAAI/bge-m3) (prod) |
| Vector Store | [FAISS](https://github.com/facebookresearch/faiss) |
| Weather API | [Open-Meteo](https://open-meteo.com) (free, no key) |
| TTS | [ai4bharat/indic-parler-tts](https://huggingface.co/ai4bharat/indic-parler-tts) |
| Framework | Python 3.11, LangChain, PyTorch |

---

## Project Status

| Phase | Description | Status |
|---|---|---|
| 1 | Project setup, config, Gradio skeleton | ✅ Complete |
| 2 | Whisper STT with auto language detection | ✅ Complete |
| 3 | IndicTrans2 translation (both directions) | ✅ Complete |
| 4 | Intent extraction + LLM answer generation | ✅ Complete |
| 5 | Crop knowledge tool (6 crops, stage-aware) | ✅ Complete |
| 6 | Weather tool (Open-Meteo, farming advisories) | ✅ Complete |
| 7 | Government scheme RAG (FAISS vector search) | ✅ Complete |
| 8 | LangChain agent — tool orchestration | 🔄 Next |
| 9 | End-to-end English pipeline test | ⏳ Pending |
| 10 | IndicTrans2 output + Indic TTS | ⏳ Pending |
| 11 | Full Gradio pipeline wiring | ⏳ Pending |
| 12 | Testing & evaluation | ⏳ Pending |
| 13 | Optimization (quantization, caching) | ⏳ Pending |
| 14 | Hugging Face Spaces deployment | ⏳ Pending |
| 15 | Documentation | ⏳ Pending |

---

## Local Setup

### Prerequisites
- Python 3.11
- Windows / Linux / macOS
- No GPU required for local dev (CPU mode)

### 1. Clone the repo

```bash
git clone https://github.com/sehscape/Farmer-Advisory-Voice-Agent.git
cd Farmer-Advisory-Voice-Agent
```

### 2. Create virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
# Edit .env — add your HF_TOKEN if you have one (optional for local dev)
```

The defaults in `.env` use stub models for fast local dev (no large downloads):

```env
USE_STUB_TRANSLATION=true   # Skip 4GB IndicTrans2 download
USE_STUB_LLM=true           # Skip HF API calls, use rule-based stub
USE_STUB_RAG=false          # Use real FAISS scheme index
```

### 5. Build the scheme index (one time)

```bash
python scripts/build_scheme_index.py
```

### 6. Run the app

```bash
python app.py
```

Open [http://127.0.0.1:7860](http://127.0.0.1:7860) in your browser.

---

## Testing

Each phase has its own test script in `scripts/`:

```bash
# Phase 2 — STT
python scripts/test_stt_phase2.py

# Phase 6 — Weather tool
python scripts/test_weather_phase6.py

# Phase 7 — Scheme RAG
python scripts/test_scheme_phase7.py
```

---

## Government Schemes in Knowledge Base

| Scheme | What it covers |
|---|---|
| **PM-KISAN** | Rs 6,000/year income support — who qualifies, how to apply, documents needed |
| **PMFBY** | Crop insurance — coverage, premium rates (as low as 1.5%), claim process |
| **Kisan Credit Card** | Agricultural loans at 4–7% interest — eligibility, benefits, insurance included |
| **Soil Health Card** | Free soil nutrient testing — 12 parameters, crop-wise fertilizer recommendations |

---

## Crops in Knowledge Base

Each crop has stage-by-stage advice covering irrigation, fertilizer, pest watch, and tips:

| Crop | Recognized in |
|---|---|
| Wheat (गेहूं / ਕਣਕ / गव्हू) | Hindi, Punjabi, Marathi |
| Rice / Paddy (धान / ਝੋਨਾ / भात) | Hindi, Punjabi, Marathi |
| Onion (प्याज / ਪਿਆਜ਼ / कांदा) | Hindi, Punjabi, Marathi |
| Tomato (टमाटर / ਟਮਾਟਰ / टोमॅटो) | Hindi, Punjabi, Marathi |
| Cotton (कपास / ਕਪਾਹ / कापूस) | Hindi, Punjabi, Marathi |
| Maize (मक्का / ਮੱਕੀ / मका) | Hindi, Punjabi, Marathi |

---

## Model Strategy

| Component | Local Dev (CPU) | HF Spaces (T4 GPU) |
|---|---|---|
| STT | whisper-tiny | whisper-large-v3 |
| Translation | Stub / IndicTrans2 | IndicTrans2 (both directions) |
| LLM | StubLLM / HF Inference API | Llama 3.1 8B (4-bit) |
| Embeddings | paraphrase-multilingual-MiniLM | BAAI/bge-m3 |
| TTS | Stub | ai4bharat/indic-parler-tts |

---

## Folder Structure

```
├── app/
│   ├── agents/          # Intent extraction, answer generation, agent state
│   ├── models/          # STT, TTS, LLM, Translation, Embeddings
│   ├── rag/             # FAISS RAG pipeline for government schemes
│   ├── tools/           # Crop tool, Weather tool, Scheme tool
│   ├── ui/              # Gradio interface
│   └── config.py        # All configuration (env-driven)
├── data/
│   ├── crops/           # JSON knowledge base for each crop
│   └── schemes/raw/     # Government scheme text files
├── scripts/             # One-off tools and test scripts
├── tests/               # Unit tests
├── app.py               # HF Spaces entry point
└── requirements.txt
```

---

## Contributing

This is an active portfolio/academic project. Contributions, suggestions, and feedback are welcome — especially on:
- Adding more crops to the knowledge base
- Adding more government scheme documents
- Improving translation quality for Marathi and Punjabi
- Testing on real farmer queries

---

<div align="center">

Built with the goal of making agricultural AI accessible to every Indian farmer, regardless of language or literacy.

**Made by [Sehal Chodankar](https://github.com/sehscape)**

</div>
