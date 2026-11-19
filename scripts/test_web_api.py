"""The web app's JSON API, end to end, through FastAPI's test client.

Runs the Render build (LITE_MODE) without a Groq key, so it needs no
credentials: typed English questions, rule-based understanding, live weather
and gTTS (internet needed for those two).

    python scripts/test_web_api.py
"""
import os
import sys
from pathlib import Path

os.environ["LITE_MODE"] = "true"
os.environ["GROQ_API_KEY"] = ""          # rule-based path, no credentials
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.utils.logging import enable_utf8_console  # noqa: E402
enable_utf8_console()

import logging  # noqa: E402
logging.disable(logging.WARNING)

from fastapi.testclient import TestClient  # noqa: E402

from app.ui.i18n import LANG_CODES, STRINGS, t  # noqa: E402
from app.web import server  # noqa: E402

results = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f"  — {detail[:120]}" if detail and not ok else ""))


def section(title: str) -> None:
    print("\n" + "=" * 64 + f"\n{title}\n" + "=" * 64)


def main() -> int:
    client = TestClient(server.create_app(with_classic=False))

    section("1. Pages and the installable app")
    page = client.get("/")
    check("/ serves the web app", page.status_code == 200 and "Agri Assistant" in page.text
          and "/static/app.js" in page.text)
    check("service worker served from the root (scope /)",
          client.get("/sw.js").headers["content-type"].startswith("application/javascript"))
    manifest = client.get("/manifest.webmanifest")
    check("web manifest with app icons", manifest.status_code == 200
          and "icon-512.png" in manifest.text and "standalone" in manifest.text)
    check("static files", all(client.get(f"/static/{name}").status_code == 200
                              for name in ("app.js", "styles.css", "icon.svg", "icon-192.png")))
    check("API docs at /api/docs", client.get("/api/docs").status_code == 200)

    section("2. Health and configuration")
    health = client.get("/api/health").json()
    check("health: ok, Lite build", health["status"] == "ok" and health["mode"].startswith("lite"))
    config = client.get("/api/config").json()
    check("four languages", [lang["code"] for lang in config["languages"]] == list(LANG_CODES))
    check("every message in every language",
          all(set(config["strings"][lang]) == set(STRINGS) for lang in LANG_CODES))
    check("sample questions and crop names per language",
          all(len(config["examples"][lang]) == 4 for lang in LANG_CODES)
          and config["crops"]["wheat"]["hi"] == "गेहूं")
    check("no Groq key → typed-only build (no microphone)", config["voice"] is False)

    section("3. Asking")
    r = client.post("/api/ask", json={"text": "When should I put fertilizer in my wheat?", "lang": "en"}).json()
    check("missing crop age → asked back, with the question remembered",
          r["missing"] == ["age"] and r["pending"] and r["answer"] == t("ask_age", "en", crop="wheat"),
          r["answer"])
    r = client.post("/api/ask", json={"text": "40 days", "lang": "en", "pending": r["pending"]}).json()
    crop = r["cards"].get("crop") or {}
    check("reply '40 days' completes it: crop tool, growth-stage card",
          r["tools"]["crop"] and crop.get("stage") == "Tillering" and crop.get("days") == 40
          and crop.get("total_days") == 120, str(crop))
    check("answer carries what to read aloud", r["speech"]["text"] and r["speech"]["lang"] == "en")

    r = client.post("/api/ask", json={"text": "Will it rain tomorrow?", "lang": "en",
                                      "location": "18.5204, 73.8567"}).json()
    weather = r["cards"].get("weather") or {}
    check("GPS position → weather card for the farmer's location",
          r["tools"]["weather"] and weather.get("gps") is True and len(weather.get("days", [])) >= 3
          and weather["now"]["temp"] is not None, str(r["cards"])[:120])

    r = client.post("/api/ask", json={"text": "How do I apply for PM-KISAN?", "lang": "en"}).json()
    check("scheme question → documents listed by their proper names",
          r["tools"]["scheme"] and "PM-KISAN" in r["cards"].get("schemes", []), str(r["cards"]))

    r = client.post("/api/ask", json={"text": "मेरी गेहूं 40 दिन की है", "lang": "hi"}).json()
    check("typed Hindi without a translator → told in Hindi to type in English",
          r["answer"] == t("err_type_english_lite", "hi"), r["answer"])

    section("4. Bad input is refused politely")
    check("empty question → 422", client.post("/api/ask", json={"text": "", "lang": "en"}).status_code == 422)
    check("overlong question → 422",
          client.post("/api/ask", json={"text": "x" * 700, "lang": "en"}).status_code == 422)
    r = client.post("/api/ask", json={"text": "Will it rain in Pune tomorrow?", "lang": "zz",
                                      "pending": {"missing": "not-a-list"}})
    check("unknown language and malformed pending are ignored, not fatal",
          r.status_code == 200 and r.json()["tools"]["weather"])
    v = client.post("/api/voice", files={"audio": ("q.webm", b"123", "audio/webm")}, data={"lang": "hi"})
    check("voice without a speech service → 400 in the farmer's language",
          v.status_code == 400 and v.json()["detail"] == t("err_no_input_lite", "hi"))

    section("5. The spoken answer")
    s = client.post("/api/speak", json={"text": "Apply 25 kg urea per acre.", "lang": "en"})
    check("speak → MP3 audio", s.status_code == 200 and s.headers["content-type"] == "audio/mpeg"
          and len(s.content) > 2000, f"{s.status_code} {len(s.content)}")
    check("speak in Hindi", client.post("/api/speak", json={"text": "नमस्ते", "lang": "hi"}).status_code == 200)

    section("6. Rate limiting")
    limit = server._RateLimit(3)
    check("a client over its per-minute budget is held back",
          [limit.allow("a") for _ in range(4)] == [True, True, True, False] and limit.allow("b"))

    passed = sum(results)
    print(f"\nResult: {passed}/{len(results)} checks passed"
          f"{' — ALL PASSED' if passed == len(results) else ''}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
