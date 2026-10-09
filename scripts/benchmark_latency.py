"""Where does the time go? Per-stage latency of real voice questions.

Each question is spoken with gTTS, then sent through the real pipeline of the
Render build (Groq Whisper → understanding → LangChain agent → Groq answer
writer → gTTS). The stage timings are read from the pipeline's own trace.

Needs GROQ_API_KEY in .env and internet; uses ~8 of your free Groq requests
per round. The key is never printed.

    python scripts/benchmark_latency.py            # one round, 4 languages
    python scripts/benchmark_latency.py --rounds 3 --json latency.json
"""
import argparse
import json
import os
import re
import statistics
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("LITE_MODE", "true")      # the Render build
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.utils.logging import enable_utf8_console  # noqa: E402
enable_utf8_console()

import logging  # noqa: E402
logging.disable(logging.WARNING)

from app.config import GROQ_API_KEY, USE_GROQ  # noqa: E402

CASES = [  # (language, spoken question)
    ("hi", "मेरी गेहूं की फसल 40 दिन की है, कौन सी खाद डालूं?"),
    ("pa", "ਕੀ ਕੱਲ੍ਹ ਲੁਧਿਆਣਾ ਵਿੱਚ ਮੀਂਹ ਪਵੇਗਾ?"),
    ("mr", "पीएम किसान योजनेसाठी कोणती कागदपत्रे लागतात?"),
    ("en", "My cotton plants have white insects under the leaves. What should I do?"),
]

# Stage → the trace line that reports it
STAGES = {
    "speech-to-text": r"^\[STT\].*· ([\d.]+)s:",
    "understanding": r"^\[Understand\] (?!english).*\(([\d.]+)s\)$",
    "agent + tools": r"^\[Agent\] done in ([\d.]+)s",
    "answer writing": r"^\[Answer\] .* answer in ([\d.]+)s",
    "words on screen": r"^\[Answer\] shown after ([\d.]+)s",
    "voice (TTS)": r"^\[TTS\] .* in ([\d.]+)s",
    "total": r"^\[Total\] response time: ([\d.]+)s",
}


def speak(text: str, lang: str) -> str:
    from gtts import gTTS
    path = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False).name
    gTTS(text=text, lang=lang).save(path)
    return path


def timings(trace: str) -> dict:
    found = {}
    for line in trace.splitlines():
        for stage, pattern in STAGES.items():
            m = re.search(pattern, line.strip())
            if m:
                found[stage] = float(m.group(1))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--json", help="also write the raw timings to this file")
    args = parser.parse_args()

    if not (GROQ_API_KEY and USE_GROQ):
        print("[SKIP] No GROQ_API_KEY found. Add it to .env (see DEPLOY.md) and run again.")
        return 0
    from app.ui import gradio_app as ga
    ga.warm_up()

    runs = []
    for n in range(args.rounds):
        for lang, question in CASES:
            r = ga._pipeline(speak(question, lang), "", "", lang)
            t = timings(r["trace"])
            runs.append({"round": n + 1, "lang": lang, **t})
            print(f"  round {n + 1} · {lang} · words {t.get('words on screen', 0):.1f}s · "
                  f"total {t.get('total', 0):.1f}s")

    print(f"\n{'stage':<18}{'median':>9}{'min':>8}{'max':>8}   (seconds, {len(runs)} questions)")
    for stage in STAGES:
        values = [run[stage] for run in runs if stage in run]
        if values:
            print(f"{stage:<18}{statistics.median(values):>9.2f}"
                  f"{min(values):>8.2f}{max(values):>8.2f}")
    if args.json:
        Path(args.json).write_text(json.dumps(runs, indent=2), encoding="utf-8")
        print(f"\nRaw timings → {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
