"""Knowledge-base test — the crop guides and scheme documents themselves.

  1. Every crop guide is complete: names in all 4 languages, growth stages
     that start at day 0 and follow on without gaps, every stage name in the
     farm glossary (so it is never machine-translated), and the fields the
     answer is built from.
  2. Every scheme in data/schemes/schemes.json has its document (overview, how
     to apply, helpline), a title, names in all 4 languages and words to
     recognise it by.
  3. A farmer's crop word in any language finds the right guide — including
     the tricky ones (a word inside another word, inflected Marathi forms,
     words that are also everyday words).
  4. A scheme named in any language finds the right document, and the keyword
     search (the one the live site runs) ranks that document first.

Usage (from project root, venv active):
    python scripts/test_knowledge.py
"""
import os
import sys
from pathlib import Path

os.environ["GROQ_API_KEY"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.utils.logging import enable_utf8_console
enable_utf8_console()

import logging
logging.disable(logging.WARNING)

from app import knowledge
from app.config import SCHEMES_RAW_DIR
from app.models.agri_glossary import stage_name

LANGS = ("en", "hi", "pa", "mr")
_failures = 0
_total = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global _failures, _total
    _total += 1
    _failures += 0 if ok else 1
    print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f"  ({detail})" if detail and not ok else ""))


# (farmer's words, language, expected crop — a guide's name, "other:<name>" or None)
CROP_WORDS = [
    ("मेरे गन्ने में कौन सी खाद डालूं?", "hi", "sugarcane"),
    ("ਮੇਰੇ ਗੰਨੇ ਨੂੰ ਕਿਹੜੀ ਖਾਦ ਪਾਵਾਂ?", "pa", "sugarcane"),
    ("माझ्या उसाला कोणते खत द्यावे?", "mr", "sugarcane"),
    ("नाशिकमध्ये उद्या पाऊस येईल का?", "mr", None),            # पाऊस (rain) is not ऊस
    ("सोयाबीन पर इल्ली लगी है", "hi", "soybean"),
    ("हरभऱ्याला घाटे अळी लागली", "mr", "chickpea"),
    ("ਛੋਲਿਆਂ ਨੂੰ ਪਾਣੀ ਕਦੋਂ ਲਾਵਾਂ?", "pa", "chickpea"),
    ("ਸਰ੍ਹੋਂ ਉੱਤੇ ਤੇਲਾ ਲੱਗ ਗਿਆ", "pa", "mustard"),
    ("मूंगफली के पत्ते पीले हैं", "hi", "groundnut"),            # not मूंग (moong)
    ("मूंग की फसल 30 दिन की है", "hi", "moong"),
    ("ਮੂੰਗੀ ਦੀ ਬਿਜਾਈ ਕਦੋਂ ਕਰਾਂ?", "pa", "moong"),
    ("माझ्या तुरीला शेंगा लागल्या", "mr", "pigeonpea"),
    ("my tur crop is 60 days old", "en", "pigeonpea"),
    ("turn the pump on at night", "en", None),                   # "turn" is not "tur"
    ("आलू में झुलसा रोग", "hi", "potato"),
    ("बटाट्याला पाणी किती द्यावे?", "mr", "potato"),
    ("मिरचीवर बोकड्या रोग", "mr", "chilli"),
    ("काली मिर्च की खेती कैसे करें?", "hi", "other:black pepper"),  # not chilli
    ("बाजरे में कौन सी खाद?", "hi", "bajra"),
    ("ज्वारीला पाणी कधी द्यावे?", "mr", "jowar"),
    ("केले के पौधे गिर रहे हैं", "hi", "banana"),
    ("माझ्या केळीची पाने पिवळी", "mr", "banana"),
    ("मी अर्ज केला पण पैसे आले नाहीत", "mr", None),               # केला = "did" in Marathi
    ("ਮੇਰੇ ਨਾਰੀਅਲ ਨੂੰ ਕਿਹੜੀ ਖਾਦ ਪਾਵਾਂ?", "pa", "other:coconut"),
    ("black gram pests", "en", "other:black gram"),              # not chickpea or moong
    ("how many grams of urea for wheat?", "en", "wheat"),       # "grams" is not a crop
    ("orange spots on my wheat leaves", "en", "wheat"),
    ("what is the price of onion today?", "en", "onion"),
    ("प्रधानमंत्री फसल बीमा योजना", "hi", None),                 # प्रधान contains धान
    ("ਨਰਮੇ ਉੱਤੇ ਚਿੱਟੀ ਮੱਖੀ", "pa", "cotton"),
]

# (question, expected scheme id)
SCHEME_WORDS = [
    ("सोलर पंप योजना क्या है?", "pm_kusum"),
    ("How do I get a solar pump under PM-KUSUM?", "pm_kusum"),
    ("ठिबक सिंचन अनुदान कसे मिळेल?", "pmksy"),
    ("drip subsidy for my banana farm", "pmksy"),
    ("PM Kisan Maandhan pension kaise milegi?", "pm_kmy"),
    ("किसान पेंशन योजना", "pm_kmy"),
    ("नमो शेतकरी योजनेचा हप्ता कधी येणार?", "namo_shetkari"),
    ("how to sell on e-NAM", "e_nam"),
    ("ਪਰਾਲੀ ਵਾਲੀ ਮਸ਼ੀਨ ਤੇ ਸਬਸਿਡੀ", "crop_residue"),
    ("Happy Seeder subsidy", "crop_residue"),
    ("पीएम किसान की किस्त कब आएगी?", "pm_kisan"),
    ("किसान क्रेडिट कार्ड कैसे बनवाएं?", "kcc"),
    ("फसल बीमा का क्लेम कैसे करें?", "pmfby"),
    ("soil health card kaise banega", "soil_health_card"),
]


def main() -> None:
    crops = knowledge.crops()
    print("=" * 64 + f"\n1. {len(crops)} crop guides\n" + "=" * 64)
    for name, data in crops.items():
        problems = []
        names = data.get("names", {})
        if set(names) != set(LANGS) or not all(names[lang].strip() for lang in LANGS):
            problems.append("names missing in some language")
        stages = data.get("stages", [])
        if not stages or stages[0]["days_range"][0] != 0:
            problems.append("stages do not start at day 0")
        for a, b in zip(stages, stages[1:]):
            if b["days_range"][0] != a["days_range"][1] + 1:
                problems.append(f"gap or overlap between '{a['name']}' and '{b['name']}'")
        for stage in stages:
            lo, hi = stage["days_range"]
            if lo > hi:
                problems.append(f"'{stage['name']}' ends before it starts")
            for field in ("description", "irrigation", "fertilizer", "watch_for", "tips"):
                if not stage.get(field):
                    problems.append(f"'{stage['name']}' has no {field}")
            for lang in ("hi", "pa", "mr"):
                if stage_name(stage["name"], lang) is None:
                    problems.append(f"'{stage['name']}' not in the glossary ({lang})")
        total = data.get("total_duration_days") or 0
        if not (stages and stages[-1]["days_range"][1] >= total > 0):
            problems.append("total_duration_days is not inside the last stage")
        if not (data.get("common_pests") and data.get("common_diseases")):
            problems.append("no pests or diseases listed")
        check(f"{name}: {len(stages)} stages, {total} days, names in 4 languages",
              not problems, "; ".join(problems))
    check("crops keep their display order (wheat first)", next(iter(crops)) == "wheat")
    check("no two crops share a farmer's word",
          len({w for n in crops for w in knowledge.crop_words(n)})
          == sum(len(knowledge.crop_words(n)) for n in crops))

    print("\n" + "=" * 64 + f"\n2. {len(knowledge.schemes())} schemes\n" + "=" * 64)
    for sid, s in knowledge.schemes().items():
        doc = Path(SCHEMES_RAW_DIR) / f"{s['file']}.txt"
        text = doc.read_text(encoding="utf-8") if doc.exists() else ""
        problems = []
        if not text.startswith("SCHEME:"):
            problems.append(f"{doc.name} missing or has no SCHEME: header")
        for section in ("OVERVIEW", "HOW TO ", "HELPLINE"):   # HOW TO APPLY / HOW TO GET …
            if text and f"\n{section}" not in text:
                problems.append(f"no {section.strip()} section")
        if set(s["names"]) != set(LANGS):
            problems.append("names missing in some language")
        if not (s["match"]["names"] and s["search"] and s["title"]):
            problems.append("no recognition words, search words or title")
        if knowledge.scheme_title(s["file"]) != s["title"]:
            problems.append("title not found from the file name")
        check(f"{sid}: {doc.name}", not problems, "; ".join(problems))
    docs = {p.stem for p in Path(SCHEMES_RAW_DIR).glob("*.txt")}
    check("every scheme document is listed in schemes.json",
          docs == {s["file"] for s in knowledge.schemes().values()}, str(docs))

    print("\n" + "=" * 64 + "\n3. Crop words in 4 languages\n" + "=" * 64)
    for text, lang, want in CROP_WORDS:
        m = knowledge.find_crop(text, lang)
        got = m.label if m else None
        check(f"[{lang}] {text[:40]} → {want}", got == want, f"got {got}")
    for raw, want in (("paddy", "rice"), ("Tur", "pigeonpea"), ("chickpeas", "chickpea"),
                      ("ਝੋਨਾ", "rice"), ("Bengal gram", "chickpea"), ("sorghum", "jowar"),
                      ("coconut", None)):
        check(f"resolve '{raw}' → {want}", knowledge.resolve_crop(raw) == want,
              str(knowledge.resolve_crop(raw)))

    print("\n" + "=" * 64 + "\n4. Schemes by name, and the live site's keyword search\n" + "=" * 64)
    for text, want in SCHEME_WORDS:
        got = knowledge.find_scheme(text)
        check(f"{text[:42]} → {want}", got == want, f"got {got}")

    from app.rag.keyword_retriever import KeywordSchemeRetriever
    bm25 = KeywordSchemeRetriever()
    bm25.build()
    for sid, s in knowledge.schemes().items():
        top = bm25.query(f"how to apply and who is eligible {s['search']}")[0]["source"]
        check(f"keyword search for {sid} ranks {s['file']} first", top == s["file"], top)

    print("\n" + "=" * 64)
    passed = _total - _failures
    print(f"Result: {passed}/{_total} checks passed — "
          f"{'ALL PASSED' if _failures == 0 else f'{_failures} FAILED'}")
    sys.exit(0 if _failures == 0 else 1)


if __name__ == "__main__":
    main()
