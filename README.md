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

[![Live demo](https://img.shields.io/badge/Live%20demo-Render-46E3B7?logo=render&logoColor=white)](https://farmer-advisory-voice-agent.onrender.com)
[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)](https://python.org)
[![Gradio](https://img.shields.io/badge/Gradio-6.x-orange?logo=gradio)](https://gradio.app)
[![LangChain](https://img.shields.io/badge/Agent-LangChain%20ReAct-1C3C3C?logo=langchain)](#-how-it-works-in-plain-english)
[![Languages](https://img.shields.io/badge/UI-English%20·%20Hindi%20·%20Punjabi%20·%20Marathi-brightgreen)](#features)
[![Status](https://img.shields.io/badge/Status-All%2015%20phases%20✅-success)](#project-status)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

🎙️ **Talk** → 🧠 **AI thinks** → 🔊 **It answers out loud**
*Crop advice · Live weather · Government schemes — grounded in real data, never made up.*

**▶ Try it live: [farmer-advisory-voice-agent.onrender.com](https://farmer-advisory-voice-agent.onrender.com)**
<sub>Free tier — the first visit after ~15 min idle takes ~1 minute to wake up.</sub>

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

The assistant transcribes it, understands it's a **fertilizer** question about **wheat at 40 days**, looks up the crop's growth stage, and **speaks back — in Hindi**:

> 🔊 *"आपकी गेहूं अभी कल्ले निकलने (टिलरिंग) की अवस्था में है। अगली सिंचाई के साथ यूरिया की दूसरी खुराक 25 किलो प्रति एकड़ डालिए…"*
> *(Your wheat is in the tillering stage. Apply the second dose of urea, 25 kg per acre, with the next irrigation…)*

Ask a bigger question — *"…and is there a scheme for irrigation?"* — and it also searches real government-scheme documents and folds that in. 🎯

Leave something out and it **asks back, out loud, in your language**:

> 👨‍🌾 *"गेहूं में खाद कब डालें?"* → 🔊 *"आपकी गेहूं की फसल कितने दिन की है? कृपया बताइए, जैसे: 40 दिन।"*
> 👨‍🌾 *"40 दिन"* → 🔊 the full answer — it remembers what you were asking.

---

## 🧠 How it works (in plain English)

Think of it as a **small shop with 7 workers**, and your question travels down the line:

```
🎙️ You speak (tap the mic, tap stop — that's it)
   │
   ▼
👂 Ears write down the words        (Whisper-large-v3)
   │
   ▼
🧐 Understand: "What is being asked? What is missing?"
   │   crop? its age? your village? weather? scheme?
   ├── something missing → ❓ ask you back, out loud, in your language
   │
   ▼
🧭 Agent picks only the workers it needs   (LangChain)
   ├── 🌱 Crop expert   (stage-by-stage advice)
   ├── 🌦️ Weather checker (live forecast)
   └── 🗂️ Scheme finder  (searches real govt documents)
   │
   ▼
🧠 Brain writes ONE clear answer, in YOUR language, from what they found
   │
   ▼
👄 Speak it aloud 🔊
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

> **Key design principle:** All tool work happens in English. Regional language appears only at the input and output boundaries. This avoids multilingual hallucination and keeps the LLM focused.
>
> **On the free Render host** the heavy boxes above run in the cloud instead: with a free
> [Groq](https://console.groq.com) key, **Whisper-large-v3** does the listening and an
> **open-weight LLM** (OpenAI's gpt-oss-120b, Apache-2.0) does the two translation steps —
> it understands the question (any of the 4 languages, even with speech-recognition
> mistakes) and writes the answer in the farmer's language **from the tool facts only**.
> The app itself stays under 200 MB of RAM.

---

## Features

| Feature | Details |
|---|---|
| **4-language interface** | A picker switches the whole screen — labels, buttons, instructions, errors — between 🇬🇧 English, 🇮🇳 Hindi, ਪੰਜਾਬੀ Punjabi and मराठी Marathi |
| **Voice questions in 4 languages** | Tap the mic, speak, tap stop — the question is sent by itself. Whisper listens in the chosen language |
| **Answers in the farmer's language** | Shown *and* spoken in Hindi / Punjabi / Marathi / English — whichever was chosen |
| **Asks back when something is missing** | No crop age → "how many days old?"; no village → "where are you?"; impossible age, unknown crop, unclear or off-topic question → a clear spoken message. The farmer can reply with just "40 days" or "Nashik" |
| **Made for farmers who can't read** | One screen, one job at a time: four big language buttons, one large microphone, the answer. Typing, location and help are folded away. Every message is spoken; the language and village are remembered on the phone; 📍 fills the location from GPS; silence or noise → "please speak again" |
| **Sample questions that ask themselves** | Four examples in the chosen language — tap one and it is asked immediately |
| **Answers that arrive quickly** | The words appear as soon as they are ready and the voice follows a moment later (speech is built in parallel); models load at startup, not on the first question |
| **LangChain agent** | A ReAct `AgentExecutor` decides which tools to call (crop / weather / scheme), with a deterministic fallback |
| **Crop Knowledge** | Wheat, Rice, Onion, Tomato, Cotton, Maize — stage-specific advice |
| **Live Weather** | Real forecast via Open-Meteo API — temperature, rain, wind + farming advisories |
| **Govt Schemes** | PM-KISAN, PMFBY crop insurance, Kisan Credit Card, Soil Health Card — refuses off-topic questions instead of guessing |
| **Voice reply** | gTTS (CPU) · ai4bharat Indic Parler TTS (GPU) |
| **Free to run** | Weather API needs no key; Groq's free plan covers voice + regional answers (no card) |

---

## Tech Stack

| Component | Technology |
|---|---|
| UI | [Gradio](https://gradio.app) 6 — 4-language interface |
| Agent | [LangChain](https://python.langchain.com) ReAct `AgentExecutor` with tool-calling |
| Speech-to-Text | [OpenAI Whisper](https://github.com/openai/whisper) — large-v3 via [Groq](https://console.groq.com) (free API) or small locally; language-forced |
| Understanding + regional answers | Open-weight LLM via Groq — [gpt-oss-120b](https://huggingface.co/openai/gpt-oss-120b) (Apache-2.0), falls back to gpt-oss-20b / Llama 3.3 70B |
| Translation (GPU build) | [IndicTrans2](https://github.com/AI4Bharat/IndicTrans2) (AI4Bharat) |
| LLM (GPU build) | [Llama 3.1 8B](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct) via HF Inference API |
| Embeddings | [paraphrase-multilingual-MiniLM](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2) (dev) / [BGE-M3](https://huggingface.co/BAAI/bge-m3) (prod) |
| Vector Store | [FAISS](https://github.com/facebookresearch/faiss) |
| Weather API | [Open-Meteo](https://open-meteo.com) (free, no key) |
| TTS | [ai4bharat/indic-parler-tts](https://huggingface.co/ai4bharat/indic-parler-tts) |
| Framework | Python 3.11, PyTorch |

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

**Beyond the 15 phases:**

| Addition | Status |
|---|---|
| LangChain ReAct agent with tool-calling (default engine) | ✅ Complete |
| 4-language interface + voice questions in every language | ✅ Complete |
| Lite build for free 512 MB hosting | ✅ Complete |
| Live deployment on Render | ✅ Live |
| Voice + answers in all 4 languages on the free host (Groq Whisper + open LLM) | ✅ Complete |
| Asks back for missing / wrong details, remembers the conversation | ✅ Complete |
| Voice-first journey: auto-send on stop, 📍 GPS, language & village remembered | ✅ Complete |

> **Agent engines.** By default a **LangChain ReAct `AgentExecutor`** runs the
> tool loop (`app/agents/langchain_agent.py`). On CPU its decisions come from a
> deterministic rule-based policy that speaks LangChain's ReAct protocol; point
> it at a real LLM (Qwen / Llama-3.1-8B / Gemma) and the model makes them. If the
> loop ever fails, the deterministic **sequential orchestrator**
> (`app/agents/orchestrator.py`) takes over — or select it with
> `AGENT_BACKEND=sequential`.

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
# For voice + answers in Hindi / Punjabi / Marathi, add GROQ_API_KEY
# (free, from console.groq.com — see DEPLOY.md). Never commit .env.
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
python scripts/test_langchain_agent.py    # LangChain agent: tool choice for 9 intents + fallback
python scripts/test_i18n.py               # 4-language UI + spoken questions in each language
python scripts/test_lite_mode.py          # Lite build runs with the heavy ML libraries absent
python scripts/test_voice_languages.py    # Render build + Groq (faked): voice, 4 languages, ask-backs, failures
python scripts/test_groq_live.py          # Same journey with your real GROQ_API_KEY (skips without one)

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

## Deployment

**Live now:** [farmer-advisory-voice-agent.onrender.com](https://farmer-advisory-voice-agent.onrender.com)
(Render, Lite build). After pushing to `main`, redeploy from the Render
dashboard: **Manual Deploy → Deploy latest commit**.

Full step-by-step guide: **[`DEPLOY.md`](DEPLOY.md)**. In short:

| Path | Cost | 24/7? | Features |
|---|---|---|---|
| **Google Colab** (`notebooks/run_full_app_colab.ipynb`) | Free | While the tab is open | **Everything** — mic in 4 languages, LangChain agent on a real LLM, semantic search, voice |
| **Render — Lite** (`render.yaml`, `LITE_MODE=true`) | Free | ✅ (sleeps when idle) | With a free `GROQ_API_KEY`: **mic + answers in all 4 languages**, ask-backs, LangChain agent, weather, crop advice, keyword scheme search, voice reply. Without the key: typed English only |
| **HF Spaces / Render Standard / GPU host** | Paid | ✅ | Everything, production models |

> Mid-2026: Hugging Face Spaces now needs a **paid plan** for Gradio apps, and
> Render's free tier is **512 MB RAM** — too small for Whisper + embeddings. The
> **Lite build** (`LITE_MODE=true` + `requirements-lite.txt`) strips PyTorch and
> the heavy models so it fits the free tier; `render.yaml` wires it up
> automatically.

**Full app on a GPU host** — set: `USE_STUB_TRANSLATION=false`, `USE_STUB_LLM=false`,
`USE_STUB_RAG=false`, `TTS_ENGINE=parler`, `WHISPER_MODEL_ID=openai/whisper-large-v3`.
The app auto-detects the GPU — no code change.

---

## Limitations

- **Regional answers need a Groq key (or IndicTrans2 on a GPU).** Without
  `GROQ_API_KEY`, the Lite build takes typed English only, and the local build
  answers in English. With the key, Groq's free plan allows about 2,000 voice
  questions a day and a few hundred thousand LLM tokens (roughly 50–60 full
  answers a day on gpt-oss-120b before it moves to the next model). Over the
  limit, the farmer hears "please wait a minute" in their language.
- **Groq sees the question.** Voice clips and question text go to Groq's API to
  be transcribed and understood (GPS coordinates don't — they only go to the
  weather service). Fine for a demo; a production deployment should self-host.
- **Speech recognition without Groq is approximate.** Local `whisper-small` garbles
  Marathi and Punjabi; a Hindi/Marathi/Punjabi farm vocabulary in the rules still
  recovers the crop, place and topic (tested on real garbled output).
- **Tool choice is rule-based.** The LangChain loop, tools and parsing are real,
  and the tool plan comes from the LLM's understanding of the question, but a
  deterministic policy drives the ReAct steps (fast, free, reliable).
- **Scheme search on the free host is keyword-based** (BM25), not semantic.
- **Knowledge coverage** is intentionally small (6 crops, 4 schemes) for the MVP.
- **Scheme faithfulness** for *topically-related but unanswerable* questions relies
  on the real LLM's judgement; the retrieval guardrail only rejects clearly
  off-topic queries.
- **gTTS** needs internet and offers a single generic voice per language.

## Future Improvements

- Self-host Whisper + an open LLM (or IndicTrans2 + Parler) on a GPU so no
  question leaves the server, with a more natural Indic voice than gTTS.
- Drive the LangChain agent's ReAct steps with Llama-3.1-8B or Gemma on a GPU
  instead of the rule-based policy.
- Accept `?lang=hi` links to share a pre-set language with farmers.
- Expand the crop and scheme knowledge bases; ingest real government PDFs with
  page-level citations.
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
