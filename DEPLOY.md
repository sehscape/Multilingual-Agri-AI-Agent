# Deployment Guide

Two ways to show this project running:

| Path | Cost | Up 24/7? | Features | Use it for |
|---|---|---|---|---|
| **A. Google Colab** | Free | ❌ Only while the tab is open | **Everything** — mic in 4 languages, LangChain agent on a real LLM, semantic search, voice | Live demo / viva |
| **B. Render (Lite)** | Free | ✅ Yes (sleeps when idle, wakes on visit) | With a free Groq key: **mic + answers in all 4 languages**, ask-backs for missing details, LangChain agent, weather, crop advice, keyword scheme search, voice reply. Without the key: typed English only | A permanent link for farmers |

**Currently live:** https://farmer-advisory-voice-agent.onrender.com (option B).
After a push to `main`, redeploy it from the Render dashboard with
**Manual Deploy → Deploy latest commit** (this service clones the public repo
without Render's GitHub app, so pushes don't trigger deploys on their own).

> **Why not the full app on a free 24/7 host?** As of mid-2026, Hugging Face
> Spaces requires a paid plan for Gradio apps, and Render's free tier gives only
> 512 MB RAM — not enough for Whisper + the embedding model (~1.5 GB). The Lite
> build drops those heavy parts so it fits, and hands the listening and the
> Hindi/Punjabi/Marathi understanding + answers to Groq's free API instead
> (section C). The fully self-hosted app needs a GPU/paid host.

---

## A. Google Colab (full app, demo link)

1. Open **`notebooks/run_full_app_colab.ipynb`** in Google Colab
   (github.com → the file → "Open in Colab", or upload it to colab.research.google.com).
2. *(Optional)* `Runtime → Change runtime type → T4 GPU`.
3. `Runtime → Run all`.
4. Wait ~5–10 min (first run installs everything + downloads models).
5. Click the `https://xxxxx.gradio.live` link the last cell prints.

The link dies when you close the tab. Re-run the last cell to get a new one.

---

## B. Render — free "Lite" 24/7 deploy

### One-time setup

1. Push this repo to GitHub (already done: `github.com/sehscape/Farmer-Advisory-Voice-Agent`).
2. Go to **https://render.com** → sign up (free, "Hobby" plan) — you can sign in with GitHub.
3. Click **New +** → **Web Service**.
4. Connect your GitHub and pick the **Farmer-Advisory-Voice-Agent** repo.
5. Render reads **`render.yaml`** automatically and fills in everything:
   - Runtime: **Python 3**
   - Build command: `pip install --upgrade pip setuptools wheel && pip install -r requirements-lite.txt`
   - Start command: `python app.py`
   - Plan: **Free**
   - Env vars: `LITE_MODE=true`, `PYTHON_VERSION=3.11.9`, and `GROQ_API_KEY`
     (Render asks you to fill it in — see section C; leave it empty for a
     typed-English-only build)
   If it doesn't auto-fill, enter those values by hand. **The build command must
   point at `requirements-lite.txt`, not `requirements.txt`** — the default is wrong.
6. Click **Create Web Service**.

> The repo also carries a `.python-version` file (3.11.9). If the build ever fails
> with `No module named 'pkg_resources'` or a numpy source build, Render picked a
> newer Python — confirm `PYTHON_VERSION=3.11.9` is set and redeploy.

### What happens next

- Render installs the lite dependencies (~2–3 min) and starts the app.
- First load builds the scheme keyword index in memory (instant).
- When the log shows `Running on http://0.0.0.0:10000`, your app is live at
  `https://farmer-advisory-voice-agent.onrender.com` (or whatever name you chose).

### Using it

- Pick a language in the top-right picker — the whole screen switches (and the
  phone remembers it next time).
- **With the Groq key (section C):** tap the microphone, ask in that language,
  tap stop — the answer appears and plays by itself, in that language. Missing
  details (crop age, village…) are asked for out loud; just answer ("40 days").
- **Without the key:** type a question in English, add a location (e.g. *Pune*),
  press **Ask**.
- Try: `How do I apply for PM-KISAN?` · `Will it rain in Nashik tomorrow?` ·
  `My wheat is 40 days old, will it rain in Pune, any scheme for irrigation?`

### Notes

- The free instance **sleeps after ~15 min** with no visitors; the next visit
  wakes it in ~30–60 s. That's normal for the free tier. **Open the link a couple
  of minutes before a demo.**
- To redeploy after a code change: `git push`, then in Render click
  **Manual Deploy → Deploy latest commit**. (Connecting Render's GitHub app
  under *Settings → Build & Deploy* turns on automatic deploys.)
- Free tier = 750 instance-hours/month (enough for one always-available service).
- Memory: the Lite build (with LangChain) uses ~170 MB of the 512 MB limit.

---

## C. Turn on voice + Hindi / Punjabi / Marathi answers (free Groq key)

Render's 512 MB can't hold a speech model, so the Lite build uses
[Groq](https://console.groq.com)'s free API for the two heavy jobs: **Whisper-large-v3**
turns the farmer's voice into text, and an **open-weight LLM** (OpenAI's gpt-oss-120b,
Apache-2.0) understands the question and writes the answer in the farmer's language —
using only the facts the app's tools found. Free plan, no credit card.

### 1. Get the key (5 minutes, one time)

1. Open **https://console.groq.com** and sign up (Google, GitHub or email).
2. In the left menu click **API Keys** → **Create API Key**.
3. Name it `farmer-advisory-agent` → **Submit**.
4. **Copy the key** (it starts with `gsk_`). Groq shows it only once — keep it
   somewhere private. **Never paste it into the code, GitHub, chat, or a screenshot.**

### 2. Give it to Render

1. **https://dashboard.render.com** → click the **farmer-advisory-voice-agent** service.
2. Left menu → **Environment** → **Add Environment Variable**.
3. Key: `GROQ_API_KEY` · Value: *paste the key* → **Save Changes**.
4. Then **Manual Deploy → Deploy latest commit** (loads the newest code with the key).
5. When the log shows `Running on http://0.0.0.0:10000`, open the site: the
   microphone is there, and the grey line under the headline says
   `voice groq whisper-large-v3 · llm groq openai/gpt-oss-120b · … · 4 languages`.

### 3. (Optional) Use it on your laptop too

Add one line to your local `.env` (this file is git-ignored — it never goes to GitHub):

```env
GROQ_API_KEY=gsk_your_key_here
```

Then check the whole journey with real voice in all 4 languages:

```bash
python scripts/test_groq_live.py
```

### Free-plan limits (as of Sept 2026)

| What | Limit | Roughly |
|---|---|---|
| Voice (Whisper-large-v3) | 20 per minute · 2,000 per day | 2,000 spoken questions a day |
| Answers (gpt-oss-120b) | 30 per minute · 8K tokens/min · 200K tokens/day | ~50 full answers a day, then gpt-oss-20b takes over automatically (its own limit) |

Over a limit, the farmer hears "many farmers are asking — please wait a minute" in
their language. If the LLM is down, the app still answers from its rules and says,
in the farmer's language, that the full answer is shown in English this time.
Models on Groq change over time; set `GROQ_LLM_MODELS` (comma-separated, tried in
order) to change them without touching code.

---

## Upgrading the Render deploy to the full app later

If you move to **Render Standard** ($25/mo, 2 GB) or another host with enough RAM:

1. Change the build command to `pip install -r requirements.txt`.
2. Remove the `LITE_MODE` env var (or set it to `false`).
3. Add: `WHISPER_MODEL_ID=openai/whisper-small`, `USE_STUB_LLM=false`,
   `USE_HF_INFERENCE_API=false`, `USE_STUB_RAG=false`, `TTS_ENGINE=gtts`.
4. Add a `packages.txt` install step for `ffmpeg` (Render: add it under
   *Settings → Build* or use a Docker deploy).
