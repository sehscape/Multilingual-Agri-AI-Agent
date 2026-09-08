---
title: Farmer Advisory Voice Agent
emoji: 🌾
colorFrom: green
colorTo: yellow
sdk: gradio
sdk_version: 4.44.0
app_file: app.py
pinned: false
license: mit
---

<div align="center">

# 🌾 Farmer Advisory Voice Agent

### *Speak your farming question. Hear real advice back — in your own language.*

[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)](https://python.org)
[![Gradio](https://img.shields.io/badge/Gradio-4.x-orange?logo=gradio)](https://gradio.app)
[![HuggingFace](https://img.shields.io/badge/🤗%20Spaces-Deploy-yellow)](https://huggingface.co)
[![Voice](https://img.shields.io/badge/Voice-Hindi%20·%20Marathi%20·%20Punjabi-brightgreen)](#)
[![Status](https://img.shields.io/badge/Status-All%2015%20phases%20✅-success)](#-project-status)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

🎙️ **Talk** → 🧠 **AI thinks** → 🔊 **It answers out loud**
*Crop advice · Live weather · Government schemes — grounded in real data, never made up.*

</div>

---

## 🌱 Why this exists

> 140+ million Indian farming households. Most speak only their regional language,
> can't wade through dense government PDFs, and have no easy way to get reliable,
> personalised farm advice — especially where literacy and connectivity are low.

A text-heavy app doesn't help someone who'd rather **just ask out loud**. So this is
**voice-first**: the farmer talks, and the assistant talks back — in Hindi, Marathi,
or Punjabi.

---

## 🎬 See it in action

> 👨‍🌾 *"मेरी गेहूं 40 दिन की है, क्या खाद डालूं?"* — **"My wheat is 40 days old, what fertilizer should I apply?"**

The assistant transcribes it, understands it's a **fertilizer** question about **wheat at 40 days**, looks up the crop's growth stage, and **speaks back**:

> 🔊 *"Your wheat is in the tillering stage. Apply the second dose of urea (25 kg/acre) with your next irrigation, watch for aphids, and remove weeds before day 35."*

Ask a bigger question — *"…and is there a scheme for irrigation?"* — and it also searches real government-scheme documents and folds that in. 🎯

---

## 🧠 How it works (in plain English)

Think of it as a **small shop with 7 workers**, and your question travels down the line:

```
🎙️ You speak
   │
   ▼
👂 Ears write down the words  (Whisper)
   │
   ▼
🌐 Translate to English       (the app thinks in English)
   │
   ▼
🧭 Router: "What is being asked?"   crop? weather? scheme?
   │        picks only the workers it needs
   ├── 🌱 Crop expert   (stage-by-stage advice)
   ├── 🌦️ Weather checker (live forecast)
   └── 🗂️ Scheme finder  (searches real govt documents)
   │
   ▼
🧠 Brain writes ONE clear answer from what they found
   │
   ▼
🌐 Translate back → 👄 Speak it aloud 🔊
```

**The golden rule:** the AI never invents facts. Scheme details come from real
documents, weather from a live API, crop advice from a curated knowledge base — the
AI only *phrases* them. No answer it can back up? It honestly says so.

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
| 8 | Agent — sequential tool orchestration | ✅ Complete |
| 9 | End-to-end English pipeline test | ✅ Complete |
| 10 | IndicTrans2 output + Indic TTS (voice) | ✅ Complete |
| 11 | Full Gradio pipeline wiring (auto-play voice) | ✅ Complete |
| 12 | Testing & evaluation framework | ✅ Complete |
| 13 | Optimization (GPU auto-detect, caching) | ✅ Complete |
| 14 | Hugging Face Spaces deployment prep | ✅ Complete |
| 15 | Documentation | ✅ Complete |

> **Note:** the agent uses a deterministic **sequential** orchestrator (intent → required tools → answer) rather than a LangChain ReAct loop — chosen for predictability, speed, and to avoid loop-induced hallucination. See `app/agents/orchestrator.py`.

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

Each phase has a smoke-test script in `scripts/`, plus a `pytest` suite:

```bash
python scripts/test_stt_phase2.py         # STT
python scripts/test_weather_phase6.py     # Weather tool
python scripts/test_scheme_phase7.py      # Scheme RAG
python scripts/test_agent_phase8.py       # Orchestrator (tool paths)
python scripts/test_pipeline_phase4to8.py # Intent → orchestrator routing
python scripts/test_e2e_phase9.py         # End-to-end: all intents + edge cases + safety
python scripts/test_tts_phase10.py        # Voice output (translate + TTS)
python scripts/test_local_llm.py          # Real open-source LLM on CPU (no GPU)

pytest -q                                 # Unit suite
```

> On Windows the scripts force UTF-8 output; if you run Python directly, set
> `PYTHONUTF8=1` so Devanagari/Gurmukhi text prints without errors.

## Evaluation

A reproducible metrics harness (spec §39) scores intent accuracy, tool selection,
RAG retrieval quality/safety, and answer groundedness — usable as a CI gate:

```bash
python scripts/evaluate.py
```

Current dev/stub baseline: intent **100%**, tool-selection **100%**,
RAG top-1 **100%** (mean relevance 0.60), off-topic refusal **100%**,
answers actionable & cited **100%**.

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
| LLM | StubLLM · **small local model on CPU** (Qwen2.5-0.5B) · HF Inference API | Llama 3.1 8B (4-bit) |
| Embeddings | paraphrase-multilingual-MiniLM | BAAI/bge-m3 |
| TTS | gTTS (`TTS_ENGINE=gtts`) — real Hi/Mr/Pa audio | ai4bharat/indic-parler-tts (`TTS_ENGINE=parler`) |

Device is auto-detected (`app/utils/device.py`): CUDA + float16 on the GPU Space,
CPU + float32 locally — no code change needed between the two.

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

## Deploying to Hugging Face Spaces

The repo is Spaces-ready:

- **`README.md`** starts with the Spaces YAML header (`sdk: gradio`, `app_file: app.py`).
- **`app.py`** is the entry point.
- **`packages.txt`** installs `ffmpeg` (needed to decode browser microphone audio).
- **`requirements.txt`** lists Python deps. For production TTS, also install
  `git+https://github.com/ai4bharat/indic-parler-tts`.

Steps:
1. Create a **Gradio** Space with a **GPU** (e.g. T4).
2. Push this repo to it.
3. In **Settings → Secrets/Variables**, set the production profile:
   ```
   USE_STUB_TRANSLATION=false
   USE_STUB_LLM=false
   USE_STUB_RAG=false
   USE_HF_INFERENCE_API=false     # or true to use the hosted Inference API
   TTS_ENGINE=parler
   WHISPER_MODEL_ID=openai/whisper-large-v3
   HF_TOKEN=...                    # if using gated models / Inference API
   ```
4. On first boot the Space downloads the models and builds/loads the FAISS index.

The app auto-uses the GPU when present; no code change between local and Space.

---

## Limitations

- **Local CPU dev speaks English.** Real regional voice needs IndicTrans2
  (`USE_STUB_TRANSLATION=false`, ~4 GB, slow on CPU) — intended for the GPU Space.
- **STT quality** depends on the Whisper size: `whisper-tiny` (dev) mishears Indic
  speech; production uses `whisper-large-v3`.
- **Knowledge coverage** is intentionally small (6 crops, 4 schemes) for the MVP.
- **Scheme faithfulness** for *topically-related but unanswerable* questions relies
  on the real LLM's judgement; the retrieval guardrail only rejects clearly
  off-topic queries.
- **gTTS** needs internet and offers a single generic voice per language.

## Future Improvements

- Enable real IndicTrans2 + Parler on the GPU Space for full regional voice.
- Expand the crop and scheme knowledge bases; ingest real government PDFs with
  page-level citations.
- Add a typed-question input for text-only / accessibility use.
- LLM-based answer faithfulness checking and citation grounding.
- Response caching and quantization (4-bit LLM) for lower latency/memory.

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



</div>
