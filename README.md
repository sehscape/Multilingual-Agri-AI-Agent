---
title: Farmer Advisory Voice Agent
emoji: 🌾
colorFrom: green
colorTo: yellow
sdk: gradio
sdk_version: 6.26.0
app_file: app.py
pinned: false
license: mit
---

<div align="center">

# 🌾 Farmer Advisory Voice Agent

### *Speak your farming question. Hear real advice back — in your own language.*

[![Live demo](https://img.shields.io/badge/Live%20demo-Render-46E3B7?logo=render&logoColor=white)](https://farmer-advisory-voice-agent.onrender.com)
[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)](https://python.org)
[![Gradio](https://img.shields.io/badge/Gradio-6.26-orange?logo=gradio)](https://gradio.app)
[![LangChain](https://img.shields.io/badge/Agent-LangChain%20ReAct-1C3C3C?logo=langchain)](#-how-it-works-in-plain-english)
[![Languages](https://img.shields.io/badge/Languages-English%20·%20Hindi%20·%20Punjabi%20·%20Marathi-brightgreen)](#features)
![License](https://img.shields.io/badge/License-MIT-green)

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
**voice-first**: the farmer picks a language, talks, and the assistant talks back —
in Hindi, Marathi, Punjabi or English.

---

## 🎬 See it in action

> 👨‍🌾 *"मेरी गेहूं 40 दिन की है, क्या खाद डालूं?"* — **"My wheat is 40 days old, what fertilizer should I apply?"**

The assistant transcribes it, understands it's a **fertilizer** question about **wheat at 40 days**, looks up the crop's growth stage, and **speaks back — in Hindi**:

> 🔊 *"आपकी गेहूं अभी कल्ले निकलने (टिलरिंग) की अवस्था में है। अगली सिंचाई के साथ यूरिया की दूसरी खुराक 25 किलो प्रति एकड़ डालिए…"*
> *(Your wheat is in the tillering stage. Apply the second dose of urea, 25 kg per acre, with the next irrigation…)*

Leave something out and it **asks back, out loud, in your language**:

> 👨‍🌾 *"गेहूं में खाद कब डालें?"* → 🔊 *"आपकी गेहूं की फसल कितने दिन की है? कृपया बताइए, जैसे: 40 दिन।"*
> 👨‍🌾 *"40 दिन"* → 🔊 the full answer — it remembers what you were asking.

**The chosen language always wins.** Ask in English with Hindi selected, and the
answer comes back in Hindi. Ask in Hindi with English selected, and it comes back
in English.

---

## 🧠 How it works (in plain English)

Think of it as a **small shop with a line of workers**; your question travels down the line:

```
🗣️ You pick a language, tap the mic, speak, tap stop
   │
   ▼
👂 Ears write down the words
   │     Whisper-large-v3 on Groq (or Whisper-small on the laptop, without a key)
   ▼
🧐 Understand: "What is being asked? What is missing?"
   │     crop? its age? your village? weather? scheme?
   ├── something missing → ❓ ask you back, out loud, in your language
   ▼
🧭 Agent calls only the workers it needs   (LangChain ReAct agent)
   ├── 🌱 Crop expert     (stage-by-stage advice from a curated knowledge base)
   ├── 🌦️ Weather checker (live 3-day forecast, Open-Meteo)
   └── 🗂️ Scheme finder   (RAG search over official scheme documents)
   ▼
🧠 Writer turns those facts into ONE answer, in YOUR language
   │     Groq LLM writes it directly, or: English answer → offline translator (NLLB)
   ▼
👄 Speak it aloud 🔊  (gTTS)
```

**The golden rule:** the AI never invents facts. Scheme details come from real
documents, weather from a live API, crop advice from a curated knowledge base — the
AI only *phrases* them. No answer it can back up? It honestly says so.

---

## What It Does

A farmer opens the page, picks a language (English · Hindi · Punjabi · Marathi), and
asks by voice or by typing — for example *"मेरी गेहूं 40 दिन की है, क्या खाद डालूं?"*

1. **Listens** — Whisper turns speech into text, *forced* to the chosen language (more reliable than guessing).
2. **Understands** — works out the crop, its age, the place, and whether the farmer wants crop care, weather or a scheme. Uses the Groq LLM, or keyword rules when there's no key.
3. **Checks what's missing** — no crop age, no village, an impossible age, a crop we don't cover → it asks back instead of guessing.
4. **Calls tools** — a LangChain agent runs the crop knowledge tool, the live weather tool and/or the scheme search.
5. **Writes the answer in the chosen language** — only from what the tools found.
6. **Speaks the answer** — the reply plays by itself.

---

## Architecture

```
                 🧑‍🌾 Farmer: picks a language, speaks or types
                                   │
                    ┌──────────────▼──────────────┐
                    │  Speech-to-text (Whisper)   │  forced to the chosen language
                    │  Groq whisper-large-v3      │  (local whisper-small if no key)
                    └──────────────┬──────────────┘
                                   │ farmer's words (any of the 4 languages)
                    ┌──────────────▼──────────────┐
                    │  Understanding              │  Groq LLM → JSON
                    │  agents/understanding.py    │  (keyword rules if no key / LLM fails)
                    └──────────────┬──────────────┘
                                   │ crop · age · place · wants weather/scheme/crop care
                    ┌──────────────▼──────────────┐
                    │  Clarify — anything missing?│── yes → ask back in the farmer's
                    │  agents/clarify.py          │         language, remember the question
                    └──────────────┬──────────────┘
                                   │ tool plan
                    ┌──────────────▼──────────────┐
                    │  LangChain ReAct agent      │  (sequential orchestrator
                    │  agents/langchain_agent.py  │   takes over if it fails)
                    └───┬─────────────┬────────┬──┘
                        ▼             ▼        ▼
                 ┌───────────┐ ┌──────────┐ ┌─────────────────┐
                 │ Crop tool │ │ Weather  │ │ Scheme RAG      │
                 │ JSON, 6   │ │ Open-    │ │ FAISS (laptop)  │
                 │ crops     │ │ Meteo    │ │ BM25 (Render)   │
                 └─────┬─────┘ └────┬─────┘ └────────┬────────┘
                       └────────────┼────────────────┘
                                    │ facts (English)
                    ┌───────────────▼─────────────┐
                    │  Answer in the chosen       │  1. Groq LLM writes it directly
                    │  language                   │  2. else English answer → NLLB
                    │  reply_writer / translation │  3. else English + a spoken notice
                    └───────────────┬─────────────┘
                                    │
                    ┌───────────────▼─────────────┐
                    │  Text-to-speech (gTTS)      │  hi · mr · pa · en
                    └───────────────┬─────────────┘
                                    ▼
                          🔊 Farmer hears the answer
```

> **Key design choice:** the tools work in English, and language only matters at
> the edges — when the farmer's words come in, and when the answer goes out. The
> farmer's **chosen language** (not the language the question happened to be asked
> in) decides the answer language, and it is carried through the whole pipeline
> as `AgentState.response_language`.

### Three ways it runs

| | Laptop + Groq key | Laptop, no key | Render free (Lite) + Groq key |
|---|---|---|---|
| Voice questions | ✅ Groq whisper-large-v3 | ✅ local whisper-small (rougher for Marathi/Punjabi) | ✅ Groq whisper-large-v3 |
| Understanding | Groq LLM | Keyword rules (know Hindi/Marathi/Punjabi farm words) | Groq LLM |
| Answer in the chosen language | ✅ Groq LLM writes it | ✅ English answer translated by NLLB (6–8 s) | ✅ Groq LLM writes it |
| If Groq fails | NLLB translates instead | — | English answer + spoken notice |
| Scheme search | FAISS (semantic) | FAISS (semantic) | BM25 (keyword) |
| Memory needed | ~3–4 GB | ~3–4 GB | under 200 MB |

Without a key, the Render build takes **typed English questions only**.

---

## Features

| Feature | Details |
|---|---|
| **4-language interface** | A picker switches the whole screen — labels, buttons, instructions, errors (87 messages × 4 languages) — between 🇬🇧 English, 🇮🇳 Hindi, ਪੰਜਾਬੀ Punjabi and मराठी Marathi |
| **Chosen-language answers** | Every answer, ask-back and spoken reply uses the chosen language, even if the question was asked in another one |
| **Voice questions** | Tap the mic, speak, tap stop — the question is sent by itself |
| **Asks back when something is missing** | No crop age → "how many days old?"; no village → "where are you?"; impossible age, unknown crop, unclear or off-topic question → a clear spoken message. The farmer can reply with just "40 days" or "Nashik" |
| **Made for farmers who can't read** | Every message is spoken; the language and village are remembered on the phone; 📍 fills the location from GPS; silence or noise → "please speak again" |
| **Quick replies** | The words appear first and the voice follows a moment later; models load at startup, not on the first question |
| **LangChain agent** | A ReAct `AgentExecutor` calls the crop / weather / scheme tools, with a deterministic fallback |
| **Crop knowledge** | Wheat, rice, onion, tomato, cotton, maize — 37 growth stages with irrigation, fertilizer, pests and tips |
| **Live weather** | Open-Meteo forecast (no key needed) plus farming advisories (heat, frost, humidity, heavy rain, storms) |
| **Government schemes** | PM-KISAN, PMFBY crop insurance, Kisan Credit Card, Soil Health Card — says "not enough information" instead of guessing |
| **Offline translation fallback** | NLLB-200 on the CPU, with a hand-written farm glossary so growth stages and headings are never mistranslated |
| **Free to run** | Weather API needs no key; Groq's free plan covers voice and regional answers (no card) |

---

## Tech Stack

| Component | Technology |
|---|---|
| UI | [Gradio](https://gradio.app) 6.26 — 4-language interface, browser mic, GPS |
| Agent | [LangChain](https://python.langchain.com) ReAct `AgentExecutor` with 3 tools |
| Speech-to-text | [Whisper](https://github.com/openai/whisper) — large-v3 via [Groq](https://console.groq.com), or small locally; language forced |
| Understanding + answers | Open-weight LLM via Groq — [gpt-oss-120b](https://huggingface.co/openai/gpt-oss-120b), falling back to gpt-oss-20b / Llama 3.3 70B |
| Rule-based fallback | Keyword router with Hindi / Marathi / Punjabi farm vocabulary (`StubLLM`) |
| Translation (no Groq) | [NLLB-200 distilled 600M](https://huggingface.co/facebook/nllb-200-distilled-600M) on CPU + hand-written glossary · [IndicTrans2](https://github.com/AI4Bharat/IndicTrans2) optional (gated, GPU) |
| RAG | Scheme documents → chunks → [paraphrase-multilingual-MiniLM](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2) embeddings → [FAISS](https://github.com/facebookresearch/faiss); pure-Python BM25 on the free host |
| Weather | [Open-Meteo](https://open-meteo.com) geocoding + forecast (free, no key) |
| Text-to-speech | [gTTS](https://github.com/pndurette/gTTS) (default) · [ai4bharat/indic-parler-tts](https://huggingface.co/ai4bharat/indic-parler-tts) optional (GPU) |
| Hosting | [Render](https://render.com) free tier (Lite build) · Google Colab notebook (full build) |
| Language | Python 3.11 |

---

## Project Status

| Phase | Description | Status |
|---|---|---|
| 1 | Project setup, config, Gradio skeleton | ✅ |
| 2 | Whisper speech-to-text | ✅ |
| 3 | IndicTrans2 translation (built; optional — NLLB is the default now) | ✅ |
| 4 | Intent extraction + answer generation | ✅ |
| 5 | Crop knowledge tool (6 crops, stage-aware) | ✅ |
| 6 | Weather tool (Open-Meteo, farming advisories) | ✅ |
| 7 | Government scheme RAG (FAISS) | ✅ |
| 8 | Agent — tool orchestration | ✅ |
| 9 | End-to-end pipeline test | ✅ |
| 10 | Output translation + text-to-speech | ✅ |
| 11 | Full Gradio pipeline wiring (auto-play voice) | ✅ |
| 12 | Testing & evaluation framework | ✅ |
| 13 | Optimization (GPU auto-detect, caching) | ✅ |
| 14 | Deployment prep | ✅ |
| 15 | Documentation | ✅ |

**Beyond the 15 phases:**

| Addition | Status |
|---|---|
| LangChain ReAct agent with tool-calling (default engine) | ✅ |
| 4-language interface + voice questions in every language | ✅ |
| Lite build for the free 512 MB host (BM25 search, no PyTorch) | ✅ |
| Voice + answers in all 4 languages via Groq | ✅ |
| Ask-backs for missing / wrong details, with follow-up memory | ✅ |
| Voice-first journey: auto-send on stop, 📍 GPS, language & village remembered | ✅ |
| Chosen-language answers without a Groq key (NLLB + farm glossary) | ✅ |
| Live deployment on Render | ✅ (needs `GROQ_API_KEY` set on the service) |

> **Agent engines.** By default a **LangChain ReAct `AgentExecutor`** runs the tool
> loop (`app/agents/langchain_agent.py`). Its steps follow the tool plan made by
> the understanding step, through a deterministic policy that speaks LangChain's
> ReAct protocol; point it at a real LLM (Qwen / Llama-3.1-8B / Gemma) and the
> model makes the decisions. If the loop ever fails, the deterministic
> **sequential orchestrator** (`app/agents/orchestrator.py`) takes over — or
> select it with `AGENT_BACKEND=sequential`.

---

## Local Setup

### Prerequisites
- Python 3.11
- Windows / Linux / macOS
- No GPU needed

### 1. Clone the repo

```bash
git clone https://github.com/sehscape/Farmer-Advisory-Voice-Agent.git
cd Farmer-Advisory-Voice-Agent
```

### 2. Create a virtual environment

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

### 4. Configure the environment

```bash
cp .env.example .env
```

Then edit `.env`:

```env
GROQ_API_KEY=gsk_...          # free from console.groq.com — voice + best answers in 4 languages
USE_STUB_TRANSLATION=false    # answers in the chosen language even without Groq (NLLB, ~2.5 GB once)
TRANSLATION_ENGINE=nllb
USE_STUB_LLM=true             # rule-based English answer template (fast, grounded)
USE_STUB_RAG=false            # use the real FAISS scheme index
TTS_ENGINE=gtts
```

Never commit `.env` — it is git-ignored.

### 5. Build the scheme index (one time)

```bash
python scripts/build_scheme_index.py
```

### 6. Run the app

```bash
python app.py
```

Open [http://127.0.0.1:7860](http://127.0.0.1:7860). Startup loads the speech model,
scheme index and (without a key) the translator in the background — 15–35 s.

---

## Testing

Each part has a test script in `scripts/`, plus a `pytest` suite. Results on the
current code (laptop, with a Groq key):

| Script | What it proves | Result |
|---|---|---|
| `test_weather_phase6.py` | Weather tool: places, forecast, advisories, failures | ✅ all pass |
| `test_scheme_phase7.py` | Scheme RAG finds the right scheme, refuses off-topic | ✅ all pass |
| `test_e2e_phase9.py` | Every intent routed to the right tools; edge cases; safety | ✅ 14/14 |
| `test_tts_phase10.py` | Voice output in all 4 languages | ✅ 11/11 |
| `test_langchain_agent.py` | Agent tool choice for 9 intents + fallback | ✅ 34/34 |
| `test_i18n.py` | 4-language screen + spoken questions in each language | ✅ 33/33 |
| `test_lite_mode.py` | Render build runs with the heavy ML libraries absent | ✅ all pass |
| `test_voice_languages.py` | Render + Groq (faked): voice, 4 languages, ask-backs, failures | ✅ 67/67 |
| `test_language_consistency.py` | Chosen language wins; glossary; "3–5 cm" never becomes "35" | ✅ 16/16 |
| `test_groq_live.py` | The same journeys with your real `GROQ_API_KEY` | ✅ all pass |
| `pytest -q` | Unit tests (speech-to-text) | ✅ 13 passed |

Other scripts: `test_stt_phase2.py`, `test_agent_phase8.py`,
`test_pipeline_phase4to8.py`, `test_local_llm.py` (a real small LLM on CPU, slow).

> On Windows, set `PYTHONUTF8=1` (or `PYTHONIOENCODING=utf-8`) so Devanagari and
> Gurmukhi print without errors.

## Evaluation

```bash
python scripts/evaluate.py
```

| Metric | Score |
|---|---|
| Intent classification accuracy | 100% (10/10) |
| Tool-selection accuracy | 100% (10/10) |
| RAG top-1 source accuracy | 100% (4/4), mean relevance 0.60 |
| RAG off-topic refusal | 100% (2/2) |
| Answers grounded / actionable / cite a source | 100% |

These are measured on a small built-in test set, so they show the pipeline is
wired correctly — not real-world accuracy.

---

## Government Schemes in Knowledge Base

| Scheme | What it covers |
|---|---|
| **PM-KISAN** | Rs 6,000/year income support — who qualifies, how to apply, documents needed |
| **PMFBY** | Crop insurance — coverage, premium rates, claim process |
| **Kisan Credit Card** | Agricultural loans at 4–7% interest — eligibility, benefits, insurance included |
| **Soil Health Card** | Free soil nutrient testing — 12 parameters, crop-wise fertilizer recommendations |

## Crops in Knowledge Base

Each crop has stage-by-stage advice covering irrigation, fertilizer, pest watch and tips:

| Crop | Stages | Recognized as |
|---|---|---|
| Wheat | 8 | गेहूं · ਕਣਕ · गहू |
| Rice / Paddy | 6 | धान · ਝੋਨਾ · भात |
| Onion | 5 | प्याज · ਪਿਆਜ਼ · कांदा |
| Tomato | 6 | टमाटर · ਟਮਾਟਰ · टोमॅटो |
| Cotton | 6 | कपास · ਕਪਾਹ · कापूस |
| Maize | 6 | मक्का · ਮੱਕੀ · मका |

---

## Model Strategy

| Component | Laptop (CPU) | Render free (Lite) | GPU host (optional) |
|---|---|---|---|
| Speech-to-text | Groq whisper-large-v3 · local whisper-small without a key | Groq whisper-large-v3 | whisper-large-v3 |
| Understanding + answer | Groq gpt-oss-120b · rules without a key | Groq gpt-oss-120b · rules without a key | Llama 3.1 8B |
| Translation fallback | NLLB-200 600M | none (too big) | IndicTrans2 |
| Embeddings / search | paraphrase-multilingual-MiniLM + FAISS | BM25 keyword search | BAAI/bge-m3 + FAISS |
| Text-to-speech | gTTS | gTTS | indic-parler-tts |

The device is auto-detected (`app/utils/device.py`): CUDA + float16 on a GPU,
CPU + float32 otherwise — no code change.

---

## Folder Structure

```
├── app/
│   ├── agents/          # understanding, clarify (ask-backs), LangChain agent,
│   │                    # orchestrator, answer writing, shared AgentState
│   ├── models/          # speech-to-text, text-to-speech, LLMs, Groq client,
│   │                    # translation (NLLB / IndicTrans2), farm glossary, embeddings
│   ├── rag/             # FAISS scheme search + BM25 keyword search
│   ├── tools/           # crop, weather and scheme tools
│   ├── ui/              # Gradio screen + all text in 4 languages (i18n.py)
│   ├── utils/           # logging, audio conversion, device detection
│   ├── config.py        # every setting, read from .env
│   └── main.py          # starts the app
├── data/
│   ├── crops/           # one JSON file per crop (stages, advice)
│   ├── schemes/raw/     # government scheme documents
│   └── vectorstore/     # built FAISS index
├── notebooks/           # Colab notebook for the full app
├── scripts/             # test scripts, evaluation, index builder
├── tests/               # pytest unit tests
├── app.py               # entry point
├── render.yaml          # Render deploy config (Lite)
├── requirements.txt     # full build
└── requirements-lite.txt# Render build (no PyTorch)
```

---

## Deployment

**Live:** [farmer-advisory-voice-agent.onrender.com](https://farmer-advisory-voice-agent.onrender.com)
(Render, Lite build). Full guide: **[`DEPLOY.md`](DEPLOY.md)**.

| Path | Cost | 24/7? | Features |
|---|---|---|---|
| **Render — Lite** (`render.yaml`, `LITE_MODE=true`) | Free | ✅ (sleeps when idle) | With `GROQ_API_KEY`: mic + answers in all 4 languages, ask-backs, agent, weather, crop advice, keyword scheme search, voice. Without it: typed English only |
| **Google Colab** (`notebooks/run_full_app_colab.ipynb`) | Free | While the tab is open | Everything, including semantic search and a local LLM |
| **Paid / GPU host** (`LITE_MODE=false`) | Paid | ✅ | Everything, plus the offline fallbacks |

**Turning on voice and regional answers on Render:**
1. Open the **web service** (not the project) → **Environment**.
2. Add `GROQ_API_KEY` with your key. *An Environment Group only works once it is
   **linked** to the service — saving the key in a group alone does nothing.*
3. **Save, rebuild, and deploy.** Pushes to `main` don't deploy by themselves:
   use **Manual Deploy → Deploy latest commit**.
4. Check the mode line under the headline: it should read
   `voice groq whisper-large-v3 · llm groq openai/gpt-oss-120b · … · 4 languages`.

> Render's free tier has 512 MB of RAM — too small for Whisper, the embedding model
> or the translator. The Lite build (`requirements-lite.txt`) drops PyTorch and
> hands listening and language work to Groq's free API.

---

## Limitations

- **Groq's free plan has daily limits** — roughly 50–60 full answers a day on
  gpt-oss-120b before it switches to smaller models; past the limits the farmer
  hears "please wait a minute" in their language. Everyone using the live link
  shares one key.
- **Groq sees the question.** Voice clips and question text go to Groq (GPS
  coordinates only go to the weather service). A production version should self-host.
- **The LLM can add small details.** It is told to use only the facts, but it
  sometimes adds a harmless-sounding step that isn't in the crop data.
- **The offline translator is literal with pest names** (e.g. "dead heart" →
  मृत हृदय) and takes 6–8 s per answer. Growth stages and headings are protected by
  the glossary.
- **No offline fallback on Render.** If Groq fails there, the farmer gets the
  English answer plus a spoken notice in their language.
- **Speech recognition without Groq is approximate** — local whisper-small garbles
  Marathi and Punjabi; the rules still recover the crop, place and topic.
- **Scheme search on the free host is keyword-based** (BM25), not semantic.
- **Small knowledge base** — 6 crops and 4 schemes.
- **gTTS** needs internet and has one generic voice per language.

## Future Improvements

- Check every dose and number in the answer against the source facts before speaking it.
- Expand the crop and scheme knowledge bases; ingest real government PDFs with page-level citations.
- Add pest and disease names to the translation glossary.
- An Android app on the same backend (started, not built yet).
- Self-host Whisper and an open LLM on a GPU so no question leaves the server, with a more natural Indic voice.
- Accept `?lang=hi` links to share a pre-set language with farmers.

---

## Contributing

This is an active portfolio/academic project. Suggestions are welcome — especially on:
- Adding more crops and government scheme documents
- Improving Marathi and Punjabi quality
- Testing on real farmer questions

---

<div align="center">

Built with the goal of making agricultural AI accessible to every Indian farmer, regardless of language or literacy.

</div>
