"""Write a spoken Hindi farming question as a WAV, for the browser tests.

Chrome can play a WAV into a page as if it were the microphone
(--use-file-for-fake-audio-capture), so scripts/e2e/buttons.test.js can ask a
real voice question. Needs internet (gTTS).

    python scripts/make_voice_sample.py      # → scripts/e2e/question_hi.wav
"""
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
from gtts import gTTS

OUT = Path(__file__).resolve().parent / "e2e" / "question_hi.wav"
QUESTION = "मेरी गेहूं की फसल चालीस दिन की है, कौन सी खाद डालूं?"


def main() -> int:
    mp3 = Path(tempfile.mkdtemp()) / "question.mp3"
    gTTS(QUESTION, lang="hi").save(str(mp3))
    data, rate = sf.read(str(mp3))
    if data.ndim > 1:
        data = data.mean(axis=1)
    pad = np.zeros(int(rate * 0.6))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # A little silence either side, like a person pausing before and after.
    sf.write(str(OUT), np.concatenate([pad, data, pad, pad]), rate, subtype="PCM_16")
    print(f"{OUT}  ({len(data) / rate:.1f} s of speech)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
