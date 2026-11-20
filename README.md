<h1 align="center">🌾 Multilingual Agri AI Agent</h1>

<p align="center">
  <a href="https://multilingual-agri-ai-agent.onrender.com"><img alt="Live demo" src="https://img.shields.io/badge/%E2%96%B6%20Live%20demo-Render-D9A441?style=for-the-badge&labelColor=08090A"></a>
  <a href="https://colab.research.google.com/github/sehscape/Multilingual-Agri-AI-Agent/blob/main/notebooks/run_full_app_colab.ipynb"><img alt="Open in Colab" src="https://img.shields.io/badge/Full%20app-Colab-F9AB00?style=for-the-badge&logo=googlecolab&logoColor=white&labelColor=08090A"></a>
  <a href="#-quality--results"><img alt="Tests" src="https://img.shields.io/badge/checks-351%20passing-2EA44F?style=for-the-badge&labelColor=08090A"></a>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white">
  <img alt="Gradio" src="https://img.shields.io/badge/Gradio-6.26-F97316?style=flat-square&logo=gradio&logoColor=white">
  <img alt="LangChain" src="https://img.shields.io/badge/LangChain-ReAct%20agent-1C3C3C?style=flat-square&logo=langchain&logoColor=white">
  <img alt="Groq" src="https://img.shields.io/badge/Groq-Whisper%20%2B%20gpt--oss--120b-F55036?style=flat-square">
  <img alt="FAISS" src="https://img.shields.io/badge/RAG-FAISS%20%7C%20BM25-0467DF?style=flat-square">
  <img alt="Languages" src="https://img.shields.io/badge/Languages-EN%20%C2%B7%20HI%20%C2%B7%20PA%20%C2%B7%20MR-D9A441?style=flat-square">
  <img alt="Knowledge" src="https://img.shields.io/badge/Knows-18%20crops%20%C2%B7%2010%20schemes-2EA44F?style=flat-square">
  <img alt="License" src="https://img.shields.io/badge/License-MIT-lightgrey?style=flat-square">
</p>

<p align="center">
  <b>Agri Assistant (कृषि सहायक) — a voice-enabled farming assistant powered by RAG, LLMs and real-time weather intelligence.</b><br>
  Pick a language, tap the big mic, ask about your crop, the weather over your field or a government scheme —<br>
  and hear a short, grounded answer back in <b>English, हिंदी, ਪੰਜਾਬੀ or मराठी</b>.
</p>

<p align="center">
  <a href="#-see-it-in-action">Demo</a> ·
  <a href="#-how-it-works">How it works</a> ·
  <a href="#-architecture">Architecture</a> ·
  <a href="#-quality--results">Results</a> ·
  <a href="#-quick-start">Quick start</a> ·
  <a href="#-deployment">Deploy</a> ·
  <a href="#-engineering-notes">Engineering notes</a>
</p>

<p align="center">
  <a href="https://multilingual-agri-ai-agent.onrender.com"><img src="assets/screenshots/app-welcome.png" alt="The live web app: the village chip and language switch (English, हिंदी, ਪੰਜਾਬੀ, मराठी) in the top bar, the greeting 'Namaste! How can I help your farm today?', a large green microphone labelled 'Tap to speak', three cards — crop care, weather, government schemes — and the question box at the bottom" width="100%"></a>
</p>
<p align="center"><sub>The live app at <a href="https://multilingual-agri-ai-agent.onrender.com">multilingual-agri-ai-agent.onrender.com</a>, unedited — one big microphone, the farmer's village and language in the top bar, and what it can help with.</sub></p>

---

## 🌾 Why I built this

India has 140+ million farming households. Good advice exists — crop calendars,
weather services, government schemes — but it sits in long English or Hindi
documents and portals. For a farmer who speaks only Marathi or Punjabi, or who
doesn't read comfortably, "go read the PM-KISAN guidelines" is not help.

So the whole product is built around one idea: **asking out loud and listening
should be enough.** Every message on screen is also spoken, the answer comes
back in the language the farmer picked, and the assistant asks back instead of
guessing when something is missing.

The second idea matters just as much: **the AI is never the source of facts.**
Fertilizer doses come from a curated crop knowledge base, weather from a live
API, scheme rules from the official documents. The language model only
understands the question and *phrases* what the tools found. If nothing
reliable is found, it says so — a wrong dose can cost a farmer a season.

## 📸 See it in action

Same live site. The page follows the device's light/dark setting, and picking a
language switches the whole screen — not just the answers.

<table>
  <tr>
    <td width="64%" align="center" valign="top"><img src="assets/screenshots/app-conversation.png" alt="A conversation in English: asked when to fertilize wheat, the assistant asks how many days old it is and offers one-tap answers; after '40 days' it answers with the urea dose and steps, a 'Crop knowledge' source chip and a card showing the Tillering stage at day 40 of 120, with Listen, Copy and WhatsApp buttons" width="100%"></td>
    <td width="36%" align="center" valign="top"><img src="assets/screenshots/phone-mic.png" alt="The app on a phone in Marathi: the greeting, a large microphone labelled बोलण्यासाठी दाबा (tap to speak), and the question box" width="100%"></td>
  </tr>
  <tr>
    <td align="center"><sub><b>Ask-back, one tap, answer</b> — “how many days old?” → <b>40 days</b> → the dose, the source, and where the crop is in its life</sub></td>
    <td align="center"><sub><b>Marathi, on a phone</b> — the mic comes first: “बोलण्यासाठी दाबा”</sub></td>
  </tr>
  <tr>
    <td align="center" valign="top"><img src="assets/screenshots/app-dark-hindi.png" alt="Dark mode in Hindi: asked whether it will rain tomorrow, with the village set to Pune, the assistant answers in Hindi from the live forecast and shows a weather card with today's temperature and the next three days" width="100%"></td>
    <td align="center" valign="top"><img src="assets/screenshots/phone-recording.png" alt="The recorder on a phone: 'ऐकत आहे… आता बोला' (listening, speak now) above a live green waveform, a timer, Cancel, and a red 'थांबवण्यासाठी दाबा' (tap to stop) button" width="100%"></td>
  </tr>
  <tr>
    <td align="center"><sub><b>Hindi, dark mode</b> — the whole page switches language; the live forecast as a card, answered and spoken in Hindi</sub></td>
    <td align="center"><sub><b>Listening</b> — a live waveform and one big red button to stop</sub></td>
  </tr>
</table>

A real exchange, spoken in Hindi:

> 👨‍🌾 *"गेहूं में खाद कब डालें?"* — *When should I put fertilizer on my wheat?*<br>
> 🔊 *"आपकी गेहूं की फसल कितने दिन की है? कृपया बताइए, जैसे: 40 दिन।"* — *How many days old is your wheat?*<br>
> 👨‍🌾 *"40 दिन"*<br>
> 🔊 *"गेहूं की 40 दिन की उम्र पर, दूसरी सिंचाई के साथ दूसरा यूरिया (25 kg/एकड़) डालें…"* — *At 40 days, apply the second urea dose (25 kg/acre) with the second irrigation…*

**The chosen language always wins.** Ask in English with Hindi selected and the
answer comes back in Hindi; the microphone also listens *for* that language
instead of guessing it.

## 🧑‍🌾 Designed for farmers

Every part of the screen is there for someone who may be using a phone in the
field, may not read comfortably, and has never used an AI app.

| On the screen | Why it's there |
|---|---|
| **"Choose your language" on the first visit** — asked in all four scripts at once | Nobody knows the farmer's language yet; the choice is then remembered on the phone |
| **One big microphone** — labelled बोलने के लिए दबाएँ, ਬੋਲਣ ਲਈ ਦਬਾਓ, बोलण्यासाठी दाबा… | Speaking is the main way in. A full-screen recorder shows a live waveform and a red *Tap to stop* |
| **Plain-language mic errors** | "Microphone permission is blocked — allow it, or type" instead of a silent, broken button |
| **Answers that talk back** | Every reply is read aloud by itself; *Listen* plays, pauses and resumes |
| **One-tap replies to ask-backs** | "How many days old?" → **20 · 40 · 60 · 90 days**; "Which village?" → **📍 Use my location**; "Which crop?" → all 18 crops, in the farmer's language |
| **Weather and crop-stage cards** | The facts behind the words: today's temperature and the next three days; *Tillering · day 40 of 120* |
| **Sources on every answer** | Crop guide, live weather or the scheme documents (named) — the assistant shows where advice came from |
| **WhatsApp and Copy on every answer** | Advice is shared the way farmers already share things |
| **📍 Your village in the top bar** | Typed once or taken from GPS, then used for every weather question |
| **Installable, opens offline** | *Add to home screen* like an app; the screen opens without signal and says when answers need the internet |
| **A KVK reminder on every page** | "For exact doses, check with your nearest Krishi Vigyan Kendra" — in all four languages |

## ✨ Highlights

| | |
|---|---|
| 🎙️ **Voice-first, 4 languages** | Whisper-large-v3 with the language forced to the farmer's choice; the whole interface (78 messages) switches between English, Hindi, Punjabi and Marathi |
| 💬 **A real conversation** | Chat thread with a typing indicator; follow-ups like *"40 days"* or *"Nashik"* complete the question that was asked back |
| 🌐 **A web app and a JSON API** | A hand-built, framework-free web app (installable, offline shell) on a FastAPI backend — `/api/ask`, `/api/voice`, `/api/speak` — so a WhatsApp bot or an Android app can use the same brain |
| 🧭 **Agentic tool use** | A LangChain ReAct `AgentExecutor` picks only the tools a question needs — crop knowledge, live weather, scheme search — with a deterministic fallback |
| 📚 **Grounded RAG with refusal** | Scheme answers come from retrieved passages; below a 0.35 relevance score it answers *"the documents don't cover this"* instead of guessing |
| ❓ **Asks back, never guesses** | Missing crop, missing age, impossible age (*wheat, 300 days*), unknown place, unsupported crop — each gets a clear spoken question |
| ⚡ **Words first, voice next** | The answer appears in a median **2.5 s**; the recording follows as a separate step, so the farmer can already ask again |
| 📱 **Made for phones** | Mic first on a small screen, language and village remembered on the device, 📍 GPS for weather, auto-send when you tap stop, dark mode |
| 🆓 **Runs on a free 512 MB host** | A *Lite* build drops PyTorch entirely and hands listening and language work to Groq's free API — ~170 MB RAM |

## 🧠 How it works

One question, end to end. Everything the pipeline learns travels in a single
`AgentState` object, including `response_language` — the language the farmer
picked, which every step respects.

```mermaid
sequenceDiagram
    autonumber
    actor F as Farmer
    participant W as Web app
    participant API as FastAPI
    participant STT as Whisper-large-v3
    participant LLM as gpt-oss-120b
    participant AG as ReAct agent
    participant T as Tools
    F->>W: taps the mic, speaks, taps stop (Hindi selected)
    W-->>F: 🎙 bubble + typing dots
    W->>API: POST /api/voice (audio, lang = hi, place, pending)
    API->>STT: audio, language = hi
    STT-->>API: "मेरी गेहूं 40 दिन की है, क्या खाद डालूं?"
    API->>LLM: understand → JSON
    LLM-->>API: crop wheat · age 40 · wants fertilizer
    API->>AG: tool plan
    AG->>T: crop_knowledge(wheat)
    T-->>AG: Tillering stage, urea 25 kg/acre, aphids…
    API->>LLM: write it in Hindi, these facts only
    LLM-->>API: Hindi answer
    API-->>W: answer · crop card · sources · what to read aloud
    W-->>F: answer + "Tillering · day 40 of 120" — words first
    Note over W,API: the voice is its own request, so the farmer reads while it loads
    W->>API: POST /api/speak
    API-->>W: MP3
    W-->>F: 🔊 plays by itself
```

## 🏗 Architecture

```mermaid
flowchart TD
    subgraph IN["🧑‍🌾 Farmer · web app (installable, offline shell)"]
        direction LR
        MIC["🎙 Voice"]
        TXT["⌨ Text"]
        GPS["📍 GPS / village"]
    end

    API["⚡ FastAPI<br/>/api/voice · /api/ask · /api/speak<br/>rate-limited · stateless"]
    STT["🎧 Speech-to-text<br/>Whisper-large-v3 on Groq · language forced"]
    U["🧐 Understanding<br/>LLM → JSON · keyword rules as fallback"]
    C{"Anything<br/>missing?"}
    ASK["❓ Ask back, out loud<br/>and remember the question"]

    subgraph AGENT["🧭 LangChain ReAct agent"]
        direction LR
        T1["🌱 crop_knowledge<br/>18 crops · 100 stages"]
        T2["🌦 weather_forecast<br/>Open-Meteo · MET Norway fallback"]
        T3["🏛 government_schemes<br/>10 schemes · FAISS or BM25 RAG"]
    end

    W["✍ Reply writer<br/>chosen language · facts only"]
    OUT["📲 Answer + cards<br/>weather · crop stage · sources"]
    V["🔊 gTTS voice → spoken reply"]

    MIC --> API
    TXT --> API
    GPS --> API
    API -- "audio" --> STT --> U
    API -- "text" --> U
    U --> C
    C -- "yes" --> ASK
    ASK -. "one-tap reply: '40 days'" .-> API
    C -- "no: tool plan" --> AGENT
    AGENT -- "facts (English)" --> W --> OUT --> V
```

**Key design choice:** the tools work in English, and language only matters at
the edges — when the farmer's words come in and when the answer goes out. That
keeps the knowledge base single-language and lets every new language reuse all
of it.

<details>
<summary><b>Asking back — the clarify step as a state machine</b></summary>

```mermaid
stateDiagram-v2
    [*] --> Understand
    Understand --> Clarify
    Clarify --> AskBack: crop, age or place missing
    Clarify --> AskBack: impossible age or unsupported crop
    Clarify --> Agent: plan complete
    AskBack --> Waiting: question kept as pending
    Waiting --> Understand: farmer replies with the detail
    Agent --> CheckResults
    CheckResults --> AskBack: place not found or scheme unknown
    CheckResults --> Answer: facts found
    Answer --> [*]
```

If only *part* of a question can be answered (say the weather, but not the
fertilizer dose without the crop's age), the assistant answers that part and
adds the missing-detail question at the end.
</details>

<details>
<summary><b>Scheme search — retrieval with a refusal threshold</b></summary>

```mermaid
flowchart LR
    D["📄 10 scheme documents"] --> CH["✂ Chunk<br/>1000 chars · 150 overlap"]
    CH --> E["🔢 Embed<br/>multilingual MiniLM-L12"]
    E --> IX[("FAISS index<br/>38 vectors")]
    Q["❓ Question"] --> QE["🔢 Embed"] --> S["Top-5 by cosine"]
    IX --> S
    S --> G{"best score<br/>≥ 0.35?"}
    G -- "yes" --> ANS["Answer from the passages<br/>+ source file"]
    G -- "no" --> REF["'The documents do not contain<br/>enough information'"]
```

On the free host there is no room for an embedding model, so a pure-Python
**BM25** index takes over (`RAG_BACKEND=bm25`) with two extra rules: a boost
when a word matches the scheme's own name, and the best chunk must match **at
least two different words** of the question — one accidental hit is not trusted.
</details>

<details>
<summary><b>Answer language — a fallback ladder that never shows the wrong script</b></summary>

```mermaid
flowchart TD
    F["Facts from the tools (English)"] --> W{"Groq LLM writes it<br/>in the chosen language"}
    W -- "right script" --> OK["✅ Shown and spoken"]
    W -- "wrong script" --> R{"Ask once more —<br/>right script now?"}
    R -- "yes" --> OK
    R -- "no" --> NL
    W -- "Groq down / no key" --> NL{"NLLB-200 on CPU<br/>+ hand-written farm glossary"}
    NL -- "available" --> OK
    NL -- "not on this host" --> EN["English advice on screen<br/>+ a spoken notice in the farmer's language"]
```
</details>

### Three ways it runs

| | 💻 Laptop + Groq key | 💻 Laptop, no key | ☁️ Render free (Lite) + Groq key |
|---|---|---|---|
| **Voice questions** | Groq Whisper-large-v3 | local Whisper-small | Groq Whisper-large-v3 |
| **Understanding** | Groq LLM | keyword rules (Hindi / Marathi / Punjabi farm words) | Groq LLM |
| **Answer in chosen language** | Groq LLM writes it | NLLB-200 translates (6–8 s) | Groq LLM writes it |
| **Scheme search** | FAISS (semantic) | FAISS (semantic) | BM25 (keyword) |
| **Memory** | ~3–4 GB | ~3–4 GB | **~170 MB** |

The device is auto-detected (`app/utils/device.py`): CUDA + float16 on a GPU,
CPU + float32 otherwise — no code change.

## 🛡 How it stays honest

| Guardrail | Where | What it prevents |
|---|---|---|
| Facts only from tools | the whole design | The LLM inventing doses, prices or rules |
| "Use only these facts" answer prompt, temperature 0 for understanding | `agents/reply_writer.py`, `agents/understanding.py` | Creative additions, inconsistent parsing |
| Relevance threshold 0.35 → refusal | `tools/scheme_tool.py` | Answering scheme questions from weak matches |
| BM25 two-word rule | `rag/keyword_retriever.py` | Trusting one accidental keyword hit |
| Ask-backs + impossible-age check | `agents/clarify.py` | Guessing a crop's stage, or advising on "wheat, 300 days" |
| Hand-written farm glossary | `models/agri_glossary.py` | "Tillering" being machine-translated as "harvest" |
| Range rewriting before translation | `models/translation.py` | "3–5 cm" of water turning into "35 cm" |
| Script check + one retry | `agents/reply_writer.py` | Punjabi shown in the wrong alphabet |
| Escaped user text, key never logged | `ui/gradio_app.py`, `models/groq_client.py` | HTML injection; leaking the API key |

## 📊 Quality & results

<p align="center">
  <img src="assets/latency.svg" alt="Latency: speech-to-text 0.7s, understanding 0.9s, agent and tools 0.5s, answer writing 0.9s, voice 1.3s; answer on screen in a median 2.45s and voice in 4.15s" width="92%">
</p>

<sub>Measured with <code>python scripts/benchmark_latency.py --rounds 2</code> — 8 real spoken questions through the Render build with Groq. Punjabi is slowest because its question needs the live weather call.</sub>

**Evaluation** (`python scripts/evaluate.py`, built-in test set):

| Metric | Score |
|---|---|
| Intent classification | **100%** (14/14) |
| Tool selection | **100%** (14/14), no unnecessary tools |
| Scheme retrieval, top-1 source | **100%** (10/10 — one question per scheme), mean relevance 0.65 |
| Off-topic refusal | **100%** (2/2) |
| Answers grounded · actionable · cite a source | **100%** |

> The test set is small, so these numbers show the pipeline is wired correctly
> end to end — they are not a claim about real-world accuracy.

**Automated checks** — every part has its own test script, a `pytest` suite, and
a browser test that presses every button of the web app in a real Chrome:

```mermaid
pie showData
    title 351 automated checks, all passing
    "Crop & scheme knowledge base" : 92
    "Voice journeys in 4 languages" : 80
    "Every button, in a real browser" : 34
    "LangChain agent + fallback" : 34
    "4-language interface" : 34
    "Web API" : 23
    "Chosen-language answers" : 16
    "End-to-end routing" : 14
    "Speech-to-text unit tests" : 13
    "Voice output" : 11
```

| Script | What it proves |
|---|---|
| `e2e/buttons.test.js` | Every button pressed in Chrome: language sheet and switch, theme, village sheet + GPS, examples, Send/Enter, one-tap ask-back replies, Listen play/pause/resume, Copy, WhatsApp, details, Retry after a failure, the mic with a **real spoken Hindi question**, Cancel/Esc, New conversation, phone layout, `?lang=` links, offline shell |
| `test_web_api.py` | The JSON API: ask-backs and `pending`, crop / weather / scheme cards, bad input refused politely, MP3 voice, rate limiting |
| `test_voice_languages.py` | The Render build with a faked Groq: voice in 4 languages, every ask-back, failure paths, the chat thread |
| `test_langchain_agent.py` | The agent picks exactly the right tools for 9 intents; the fallback takes over when the agent misbehaves |
| `test_knowledge.py` | Every crop guide and scheme document is complete (stages without gaps, every stage name in the glossary, names in 4 scripts); crop words in 4 languages find the right guide — including *पाऊस* (rain) ≠ *ऊस* (sugarcane), *मूंगफली* ≠ *मूंग*, Marathi *केला* ("did") ≠ banana; the keyword search ranks each scheme's own document first |
| `test_i18n.py` | Every string exists in all 4 languages; switching language re-renders the page |
| `test_language_consistency.py` | The chosen language wins; glossary terms survive; "3–5 cm" never becomes "35" |
| `test_e2e_phase9.py` | Every intent is routed to the right tools; odd and empty inputs don't crash |
| `test_lite_mode.py` | The free-host build runs with PyTorch and friends absent |
| `test_weather_phase6.py` · `test_scheme_phase7.py` | Live weather and scheme retrieval, including graceful failures |
| `test_groq_live.py` | The same journeys against the real Groq API with your key |

## 🧰 Tech stack

| Layer | Technology |
|---|---|
| **Web app** | Hand-written HTML/CSS/JS, no framework (~35 KB): MediaRecorder + Web Audio waveform, service worker (installable PWA, offline shell), light/dark, 4-language i18n from one source |
| **API** | [FastAPI](https://fastapi.tiangolo.com) + uvicorn — `/api/ask`, `/api/voice`, `/api/speak`, `/api/config`, `/api/health`, OpenAPI docs; per-visitor rate limits |
| **Classic screen** | [Gradio](https://gradio.app) 6.26, mounted at `/classic` on the same pipeline |
| **Agent** | [LangChain](https://python.langchain.com) ReAct `AgentExecutor` with 3 tools · deterministic sequential orchestrator as fallback |
| **Speech-to-text** | [Whisper](https://github.com/openai/whisper) large-v3 via [Groq](https://console.groq.com) · Whisper-small locally |
| **Understanding + answers** | Open-weight [gpt-oss-120b](https://huggingface.co/openai/gpt-oss-120b) on Groq, falling back to gpt-oss-20b → Llama 3.3 70B · rule-based router offline |
| **Retrieval** | [paraphrase-multilingual-MiniLM-L12-v2](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2) + [FAISS](https://github.com/facebookresearch/faiss) · pure-Python BM25 on the free host |
| **Translation (offline)** | [NLLB-200 distilled 600M](https://huggingface.co/facebook/nllb-200-distilled-600M) + hand-written glossary · [IndicTrans2](https://github.com/AI4Bharat/IndicTrans2) optional |
| **Weather** | [Open-Meteo](https://open-meteo.com) geocoding + forecast, [MET Norway](https://api.met.no) as fallback — both free, no key; forecasts cached 15 min |
| **Text-to-speech** | [gTTS](https://github.com/pndurette/gTTS), chunks fetched in parallel · [indic-parler-tts](https://huggingface.co/ai4bharat/indic-parler-tts) optional on GPU |
| **Hosting** | [Render](https://render.com) free tier (Lite build) · Google Colab (full build) |

## 📚 What it knows

**18 crops, 100 growth stages.** Every stage has irrigation, a per-acre fertilizer
dose, what to watch for and tips; every crop has its common pests and diseases
with the control measure.

| | Crops |
|---|---|
| 🌾 Cereals & millets | wheat · rice · maize · bajra · jowar |
| 🫘 Pulses | chickpea (chana) · pigeon pea (tur, arhar) · moong |
| 🌻 Oilseeds | soybean · mustard · groundnut |
| 💰 Cash crops | cotton · sugarcane |
| 🥔 Vegetables & fruit | onion · tomato · potato · chilli · banana |

Crops are recognised in all four scripts, by the words farmers actually say —
*ਨਰਮਾ* for cotton in Punjab, *उसाला* (an inflected *ऊस*) for sugarcane in
Marathi, *तुरीला* for tur. A crop the guide doesn't cover (coconut, grapes…) is
named back to the farmer with the list of crops it does know.

**10 government schemes**, each from its official description:

| Scheme | What the farmer gets |
|---|---|
| PM-KISAN | Rs 6,000 a year, in three installments |
| PM Fasal Bima Yojana | Crop insurance at a low premium |
| Kisan Credit Card | Low-interest crop loans |
| Soil Health Card | A free soil test with fertilizer advice |
| PM-KUSUM | Solar pumps — 30% central + at least 30% state subsidy |
| PMKSY Per Drop More Crop | Drip and sprinkler — 55% subsidy for small farmers, 45% for others |
| PM Kisan Maandhan | A pension of Rs 3,000 a month after 60 |
| e-NAM | Online bidding in the mandi, payment straight to the bank |
| Crop Residue Management | 50% subsidy on stubble machines (80% for custom hiring centres) |
| Namo Shetkari Mahasanman Nidhi | Maharashtra's extra Rs 6,000 a year on top of PM-KISAN |

Everything above comes from one registry (`app/knowledge.py`): **adding a crop
is one JSON file** in `data/crops/`, and **adding a scheme is one text file**
plus an entry in `data/schemes/schemes.json`. The rule router, the LLM prompt,
the quick-reply chips and every "I can help with…" message pick it up from
there, and `scripts/test_knowledge.py` checks the new file is complete.

## 🔌 API

The web app is one client of a small JSON API — a WhatsApp bot, an IVR line or
an Android app can use the same brain. Interactive docs: **`/api/docs`**.

| Endpoint | In | Out |
|---|---|---|
| `POST /api/ask` | `{text, lang, location, pending}` | answer, `missing` details, `pending`, sources, cards, what to read aloud |
| `POST /api/voice` | multipart: `audio` (webm / m4a / ogg / wav) + `lang`, `location`, `pending` | the same, plus `heard` — the words Whisper heard |
| `POST /api/speak` | `{text, lang}` | MP3 |
| `GET /api/config` | — | languages, every message in 4 languages, sample questions, crop names |
| `GET /api/health` | — | status and the engines switched on |

```bash
curl -s https://multilingual-agri-ai-agent.onrender.com/api/ask \
  -H "Content-Type: application/json" \
  -d '{"text": "My wheat is 40 days old, which fertilizer?", "lang": "hi"}'
```

The server keeps no session: when it asks back ("how many days old?"), the
question travels to the client as `pending` and returns with the reply.

## 🚀 Quick start

**Prerequisites:** Python 3.11, no GPU needed. A free [Groq API key](https://console.groq.com) is optional but turns on voice and the best answers in all four languages.

```bash
git clone https://github.com/sehscape/Multilingual-Agri-AI-Agent.git
cd Multilingual-Agri-AI-Agent
python -m venv venv
```

```bash
# Windows: venv\Scripts\activate    ·    Linux / macOS:
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # then put your key in GROQ_API_KEY
python scripts/build_scheme_index.py   # one time: builds the FAISS index
python app.py
```

Open <http://127.0.0.1:7860> — the web app. The classic Gradio screen is at
`/classic` and the API docs at `/api/docs`. Models load in the background on
startup (15–35 s); `/api/health` shows exactly what's switched on, e.g.
`full · voice groq whisper-large-v3 · llm groq openai/gpt-oss-120b · agent langchain · rag faiss · tts gtts · 4 languages`.

Browser tests (Node 18+ and Chrome):

```bash
npm install
python scripts/make_voice_sample.py      # a spoken Hindi question for the mic tests
npm run test:e2e -- http://127.0.0.1:7860/
```

<details>
<summary><b>Configuration</b> — every setting is read from <code>.env</code> by <code>app/config.py</code></summary>

| Variable | Default | What it does |
|---|---|---|
| `GROQ_API_KEY` | — | Turns on Groq Whisper and the Groq LLM (voice + 4-language answers) |
| `GROQ_LLM_MODELS` | `openai/gpt-oss-120b,openai/gpt-oss-20b,llama-3.3-70b-versatile` | Models tried in order; over-limit ones are skipped |
| `LITE_MODE` | `false` | `true` on the 512 MB host: no PyTorch, BM25 search |
| `AGENT_BACKEND` | `langchain` | `langchain` (ReAct) or `sequential` |
| `RAG_BACKEND` | `faiss` | `faiss` (semantic) or `bm25` (keyword) |
| `RAG_MIN_SCORE` · `TOP_K` | `0.35` · `5` | Retrieval threshold and depth |
| `STT_BACKEND` | `auto` | `auto`, `groq` or `local` |
| `TRANSLATION_ENGINE` | `nllb` | Offline translator when Groq can't write the answer |
| `TTS_ENGINE` | `gtts` | `gtts`, `parler` (GPU) or `stub` |
| `DEV_MODE` | `true` (`false` in Lite) | Adds the full pipeline trace to each answer's ⓘ details |
| `UI` | `web` | `web` (web app + API, Gradio at `/classic`) or `classic` (Gradio on its own, with a temporary public link) |

On Windows, set `PYTHONUTF8=1` so test scripts print Devanagari and Gurmukhi cleanly.
</details>

## ☁️ Deployment

| Path | Cost | Always on | What you get |
|---|---|---|---|
| **Render — Lite** (`render.yaml`) | Free | ✅ sleeps when idle | Mic + answers in all 4 languages with `GROQ_API_KEY`; typed English without it |
| **Google Colab** (`notebooks/run_full_app_colab.ipynb`) | Free | while the tab is open | Everything, including semantic search and a local LLM |
| **Any 2 GB+ host** (`LITE_MODE=false`) | Paid | ✅ | Everything, plus the offline fallbacks |

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/sehscape/Multilingual-Agri-AI-Agent)

Render reads `render.yaml`, installs `requirements-lite.txt` (no PyTorch) and
asks for `GROQ_API_KEY` — paste it into Render's environment settings, never into
the code. Step-by-step guide, free-tier limits and troubleshooting:
**[DEPLOY.md](DEPLOY.md)**.

## 🔧 Engineering notes

The problems that took the most thought, and what I did about them:

| Problem | Why it happened | Fix |
|---|---|---|
| Render's free tier couldn't hold the models | 512 MB RAM vs. several GB for Whisper + embeddings + translator | A `LITE_MODE` build: no PyTorch, BM25 search, Groq for listening and language — ~170 MB |
| Whisper misheard short Hindi clips as other languages | Auto-detection is unreliable on a few seconds of speech | Force the language the farmer picked, and give Groq Whisper a farm-word prompt |
| Local Whisper looped "अगर अगर अगर…" for ~40 s | A known repetition failure on CPU | Length cap, repetition penalty and a degenerate-output detector — and a "please speak again" |
| NLLB translated "tillering" as "harvest" and "3–5 cm" as "35 cm" | A general model doesn't know farm terms and drops dashes | Growth stages and headings come from a hand-written glossary; ranges are rewritten as "3 to 5" first |
| The voice took 11.5 s | gTTS accepts ~100 characters per request | Split the text and fetch the pieces in parallel → ~1.3 s |
| A follow-up asked while the voice was being made was silently dropped | Words and voice shared one event, so the page stayed "busy" | Words and voice are separate events; a newer question makes a late recording stand down |
| Loading spinners stacked on top of the answer | Gradio draws an overlay on every output of a running event | A chat thread with its own typing bubble; overlays off |
| The page scrolled sideways on phones | The audio waveform is drawn at fixed pixels per second | `contain: inline-size` on the player and thread; phone gutters set outside Gradio's CSS rewriting |
| IndicTrans2 tooling wouldn't install on Windows | It needs the MSVC build tools | A pure-Python replacement for the text processor (`indic_processor.py`) |
| Gradio's recorder only says "Record" / "Stop", in English | Its buttons can't be relabelled from Python | The big mic button's words come from CSS, generated from the same translations as the rest of the screen and keyed on the page's `lang` attribute |
| On a real phone the mic looked broken | Gradio's recorder printed "No microphone found" until permission was granted, and had share/download icons that did nothing useful | A recorder of my own (MediaRecorder + a live Web Audio waveform) that asks for permission on tap and explains a blocked or missing mic in the farmer's language |
| Phones refused to play the spoken answer | Autoplay rules: the reply arrives seconds after the tap, outside the "user gesture" | Play a 44-byte silent WAV on the first tap, which unlocks the audio element for later answers |
| WhatsApp shares lost their emoji | `wa.me` redirects through a decode that garbles them | Link to `api.whatsapp.com/send` directly — Hindi, Punjabi and Marathi all survive |
| The free host sleeps; the first visit looked dead | Render stops idle free instances | A service-worker shell that opens at once, config retried with back-off, and a "waking up" note on a slow first answer |
| Weather worked on my laptop but failed on Render | Open-Meteo rate-limits the outbound IPs that free cloud hosts share | Fall back to MET Norway, reshaped into the same format; cache forecasts for 15 min; a lookup outage is reported as "service down", never "place not found" |

## 📁 Project structure

```
├── app/
│   ├── agents/       understanding, clarify (ask-backs), LangChain agent, orchestrator,
│   │                 answer writing, shared AgentState
│   ├── models/       speech-to-text, text-to-speech, LLMs, Groq client,
│   │                 translation (NLLB / IndicTrans2), farm glossary, embeddings
│   ├── rag/          FAISS scheme search · BM25 keyword search
│   ├── tools/        crop, weather and scheme tools
│   ├── ui/           the question pipeline, the classic Gradio screen,
│   │                 and every message in 4 languages (i18n.py)
│   ├── web/          FastAPI server (server.py) and the web app (static/:
│   │                 index.html, styles.css, app.js, service worker, manifest)
│   ├── utils/        logging, audio conversion, device detection
│   ├── knowledge.py  the crops and schemes it knows — one registry for the whole app
│   ├── config.py     every setting, read from .env
│   └── main.py       starts the app
├── data/
│   ├── crops/        one JSON file per crop — names, stages and advice
│   └── schemes/      schemes.json (names, search words) + raw/ scheme documents
├── notebooks/        Colab notebook for the full app
├── scripts/          test scripts, evaluation, latency benchmark, index builder;
│                     e2e/ — the browser test (npm run test:e2e)
├── tests/            pytest unit tests
├── assets/           README images
├── app.py            entry point
├── render.yaml       Render blueprint (Lite build)
├── requirements.txt       full build
└── requirements-lite.txt  free-host build (no PyTorch)
```

## 🧭 Limitations & roadmap

**Known limitations**
- Groq's free plan allows roughly 50–60 full answers a day on gpt-oss-120b before it falls back to smaller models; everyone on the live link shares one key.
- Voice clips and question text go to Groq (GPS coordinates only go to the weather service). A production version should self-host.
- The LLM occasionally adds a harmless-sounding step that isn't in the crop data.
- The crop guides (18 crops) and scheme documents (10 schemes) are hand-written from standard package-of-practice guides and official scheme descriptions. Doses are general — every answer points to the local KVK — and scheme amounts change, so the documents need a yearly review. gTTS needs internet and has one voice per language.

**Next**
- [ ] Check every number in an answer against the source facts before speaking it
- [x] 18 crops and 10 schemes from one registry — a new crop is one JSON file
- [ ] Ingest scheme updates from the official PDFs with page-level citations
- [ ] Pest and disease names in the translation glossary
- [ ] Self-hosted Whisper + an open LLM on a GPU, and a more natural Indic voice
- [ ] A WhatsApp bot on the same `/api/voice` endpoint
- [x] Shareable `?lang=hi` links that open in a chosen language

---

<p align="center">
  Built by <a href="https://github.com/sehscape"><b>Sehal Chodankar</b></a> · MIT licensed<br>
  <sub>Made so that the best farming advice is one spoken question away — in any language, for anyone who can talk.</sub>
</p>
