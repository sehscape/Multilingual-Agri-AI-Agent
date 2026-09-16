"""Fixed farm wording for the machine-translated answer.

A general translation model knows everyday language but not crop science: it
turned "tillering" into "harvest" in Hindi and Marathi. A farmer who hears
"your wheat is at harvest" at 40 days would act on it, so the words that carry
the advice — growth stages and the answer's section labels — are written here
once, by hand, and never left to the model.
"""
from __future__ import annotations

# Section labels of the rule-based English answer (app/models/llm.py).
HEADINGS: dict[str, dict[str, str]] = {
    "Situation": {"hi": "स्थिति", "mr": "सद्यस्थिती", "pa": "ਸਥਿਤੀ"},
    "What you should do": {"hi": "आपको क्या करना चाहिए", "mr": "तुम्ही काय करावे",
                           "pa": "ਤੁਹਾਨੂੰ ਕੀ ਕਰਨਾ ਚਾਹੀਦਾ ਹੈ"},
    "Irrigation": {"hi": "सिंचाई", "mr": "पाणी देणे", "pa": "ਸਿੰਚਾਈ"},
    "Fertilizer": {"hi": "खाद", "mr": "खत", "pa": "ਖਾਦ"},
    "Watch for": {"hi": "इन पर नज़र रखें", "mr": "याकडे लक्ष ठेवा", "pa": "ਇਨ੍ਹਾਂ 'ਤੇ ਨਜ਼ਰ ਰੱਖੋ"},
    "Tips": {"hi": "सुझाव", "mr": "सल्ला", "pa": "ਸੁਝਾਅ"},
    "Weather advisory": {"hi": "मौसम सलाह", "mr": "हवामान सल्ला", "pa": "ਮੌਸਮ ਸਲਾਹ"},
    "Government scheme information": {"hi": "सरकारी योजना की जानकारी",
                                      "mr": "सरकारी योजनेची माहिती",
                                      "pa": "ਸਰਕਾਰੀ ਯੋਜਨਾ ਦੀ ਜਾਣਕਾਰੀ"},
    "Important": {"hi": "ज़रूरी", "mr": "महत्त्वाचे", "pa": "ਜ਼ਰੂਰੀ"},
    "Source": {"hi": "स्रोत", "mr": "स्रोत", "pa": "ਸਰੋਤ"},
}

# Growth-stage words used in data/crops/*.json ("Transplanting / Early
# Vegetative" is looked up part by part). Longest names are matched first.
STAGES: dict[str, dict[str, str]] = {
    "Active Tillering": {"hi": "तेज़ी से कल्ले निकलना", "mr": "जोमाने फुटवे येणे", "pa": "ਤੇਜ਼ੀ ਨਾਲ ਬੂਝਾ ਮਾਰਨਾ"},
    "Tillering": {"hi": "कल्ले निकलना", "mr": "फुटवे येणे", "pa": "ਬੂਝਾ ਮਾਰਨਾ"},
    "Crown Root Initiation (CRI)": {"hi": "शिखर जड़ बनना (CRI)", "mr": "मुकुटमुळे फुटणे (CRI)",
                                    "pa": "ਤਾਜ ਜੜ੍ਹਾਂ ਬਣਨਾ (CRI)"},
    "Jointing": {"hi": "गांठ बनना", "mr": "कांडी धरणे", "pa": "ਗੰਢਾਂ ਬਣਨਾ"},
    "Stem Extension": {"hi": "तना बढ़ना", "mr": "खोड वाढणे", "pa": "ਤਣਾ ਵਧਣਾ"},
    "Booting": {"hi": "गोभ अवस्था", "mr": "पोटरी अवस्था", "pa": "ਗੋਭ ਅਵਸਥਾ"},
    "Flag Leaf": {"hi": "ध्वज पत्ती", "mr": "ध्वज पान", "pa": "ਝੰਡਾ ਪੱਤਾ"},
    "Heading": {"hi": "बाली निकलना", "mr": "ओंबी येणे", "pa": "ਸਿੱਟੇ ਨਿਕਲਣਾ"},
    "Flowering": {"hi": "फूल आना", "mr": "फुलोरा", "pa": "ਫੁੱਲ ਪੈਣਾ"},
    "Grain Filling": {"hi": "दाना भरना", "mr": "दाणे भरणे", "pa": "ਦਾਣੇ ਭਰਨਾ"},
    "Dough Stage": {"hi": "दाना सख्त होना", "mr": "दाणे घट्ट होणे", "pa": "ਦਾਣੇ ਸਖ਼ਤ ਹੋਣਾ"},
    "Ripening": {"hi": "पकना", "mr": "पिकणे", "pa": "ਪੱਕਣਾ"},
    "Maturity": {"hi": "पकने की अवस्था", "mr": "पक्वता", "pa": "ਪੱਕਣ ਦੀ ਅਵਸਥਾ"},
    "Harvest": {"hi": "कटाई", "mr": "काढणी", "pa": "ਵਾਢੀ"},
    "Germination": {"hi": "अंकुरण", "mr": "उगवण", "pa": "ਪੁੰਗਰਨਾ"},
    "Emergence": {"hi": "पौधे निकलना", "mr": "रोपे वर येणे", "pa": "ਬੂਟੇ ਨਿਕਲਣਾ"},
    "Nursery": {"hi": "नर्सरी", "mr": "रोपवाटिका", "pa": "ਪਨੀਰੀ"},
    "Seedling": {"hi": "छोटा पौधा", "mr": "रोप अवस्था", "pa": "ਛੋਟੇ ਬੂਟੇ"},
    "Transplanting": {"hi": "रोपाई", "mr": "पुनर्लागवड", "pa": "ਲੁਆਈ"},
    "Establishment": {"hi": "पौधे जमना", "mr": "रोपे स्थिरावणे", "pa": "ਬੂਟੇ ਜੰਮਣਾ"},
    "Early Vegetative": {"hi": "शुरुआती बढ़वार", "mr": "सुरुवातीची वाढ", "pa": "ਸ਼ੁਰੂਆਤੀ ਵਾਧਾ"},
    "Vegetative Growth": {"hi": "पत्तों-तनों की बढ़वार", "mr": "पाने-खोडाची वाढ", "pa": "ਪੱਤਿਆਂ-ਤਣਿਆਂ ਦਾ ਵਾਧਾ"},
    "Vegetative": {"hi": "पत्तों-तनों की बढ़वार", "mr": "पाने-खोडाची वाढ", "pa": "ਪੱਤਿਆਂ-ਤਣਿਆਂ ਦਾ ਵਾਧਾ"},
    "Panicle Initiation": {"hi": "बाली बनना शुरू", "mr": "लोंबी तयार होऊ लागणे", "pa": "ਮੁੰਜਰਾਂ ਬਣਨੀਆਂ ਸ਼ੁਰੂ"},
    "Boll Formation": {"hi": "टिंडे बनना", "mr": "बोंडे लागणे", "pa": "ਟੀਂਡੇ ਬਣਨਾ"},
    "Boll Maturation": {"hi": "टिंडे पकना", "mr": "बोंडे पक्व होणे", "pa": "ਟੀਂਡੇ ਪੱਕਣਾ"},
    "Squaring": {"hi": "पुड़ी (कली) बनना", "mr": "पाते लागणे", "pa": "ਡੋਡੀਆਂ ਬਣਨਾ"},
    "Flower Bud Formation": {"hi": "फूल की कलियाँ बनना", "mr": "फुलकळ्या येणे", "pa": "ਫੁੱਲ ਡੋਡੀਆਂ ਬਣਨਾ"},
    "Bulb Development": {"hi": "कंद बढ़ना", "mr": "कांदा पोसणे", "pa": "ਗੰਢੀ ਬਣਨਾ"},
    "Fruit Set": {"hi": "फल लगना", "mr": "फळधारणा", "pa": "ਫਲ ਲੱਗਣਾ"},
    "Development": {"hi": "फल बढ़ना", "mr": "फळ वाढणे", "pa": "ਫਲ ਵਧਣਾ"},
    "Tasseling": {"hi": "नर मंजरी निकलना", "mr": "तुरा येणे", "pa": "ਝੰਡੇ ਨਿਕਲਣਾ"},
    "Silking": {"hi": "भुट्टे के रेशे निकलना", "mr": "कणसाला रेशीम येणे", "pa": "ਛੱਲੀ ਦੇ ਰੇਸ਼ੇ ਨਿਕਲਣਾ"},
}

_STAGE_WORD = {"hi": "अवस्था", "mr": "अवस्था", "pa": "ਅਵਸਥਾ"}
_DAYS = {"hi": "दिन", "mr": "दिवस", "pa": "ਦਿਨ"}


def stage_name(name: str, lang: str) -> str | None:
    """'Transplanting / Early Vegetative (days 26–45)' in `lang`, or None if
    any part of the stage name is not in the glossary."""
    import re

    m = re.match(r"^(.*?)\s*(\(days?\s*([\d–-]+)\))?\s*$", name.strip())
    base, days = m.group(1), m.group(3)
    extra = ""
    code = re.search(r"\((V\d+[–-]V\d+)\)\s*$", base)
    if code:  # maize "Seedling (V3–V6)"
        base, extra = base[:code.start()].strip(), f" ({code.group(1)})"
    parts = []
    for part in (p.strip() for p in base.split("/")):
        word = STAGES.get(part, {}).get(lang)
        if word is None:
            return None
        parts.append(word)
    text = " / ".join(parts) + extra
    if days:
        text += f" ({days} {_DAYS[lang]})"
    return text


def stage_word(lang: str) -> str:
    return _STAGE_WORD[lang]
