"""UI translations — every piece of on-screen text in English, Hindi, Punjabi, Marathi.

The language picked on the page drives the whole interface: labels, buttons,
instructions, placeholders, tool status, error messages and voice prompts.
The farmer's question and the agent's answer are content, not UI; see
app/ui/gradio_app.py for how voice questions in each language are handled.

Keep every key present in all four languages — scripts/test_i18n.py checks it.
"""
from __future__ import annotations

# Picker labels — exactly as shown on the page — and their language codes.
LANG_CHOICES = [
    ("🇬🇧 English", "en"),
    ("🇮🇳 Hindi", "hi"),
    ("ਪੰਜਾਬੀ Punjabi", "pa"),
    ("मराठी Marathi", "mr"),
]
LANG_CODES = tuple(code for _, code in LANG_CHOICES)
DEFAULT_LANG = "en"

# Language names, written in each UI language: LANG_NAMES[ui_lang][lang].
LANG_NAMES = {
    "en": {"en": "English", "hi": "Hindi", "pa": "Punjabi", "mr": "Marathi"},
    "hi": {"en": "अंग्रेज़ी", "hi": "हिन्दी", "pa": "पंजाबी", "mr": "मराठी"},
    "pa": {"en": "ਅੰਗਰੇਜ਼ੀ", "hi": "ਹਿੰਦੀ", "pa": "ਪੰਜਾਬੀ", "mr": "ਮਰਾਠੀ"},
    "mr": {"en": "इंग्रजी", "hi": "हिंदी", "pa": "पंजाबी", "mr": "मराठी"},
}

STRINGS: dict[str, dict[str, str]] = {
    # ── Header & hero ────────────────────────────────────────────────────────
    "brand": {
        "en": "Agri Assistant", "hi": "कृषि सहायक",
        "pa": "ਖੇਤੀ ਸਹਾਇਕ", "mr": "कृषी सहाय्यक",
    },
    "lang_picker": {"en": "Language", "hi": "भाषा", "pa": "ਭਾਸ਼ਾ", "mr": "भाषा"},
    "hero_eyebrow": {
        "en": "For Indian farmers", "hi": "भारतीय किसानों के लिए",
        "pa": "ਭਾਰਤੀ ਕਿਸਾਨਾਂ ਲਈ", "mr": "भारतीय शेतकऱ्यांसाठी",
    },
    "hero_title": {  # HTML — <em> marks the accented phrase
        "en": "Ask in your<br><em>own language.</em>",
        "hi": "पूछिए<br><em>अपनी भाषा में।</em>",
        "pa": "ਪੁੱਛੋ<br><em>ਆਪਣੀ ਭਾਸ਼ਾ ਵਿੱਚ।</em>",
        "mr": "विचारा<br><em>तुमच्या भाषेत.</em>",
    },
    "hero_body_full": {
        "en": "Ask about your crop, the weather over your field, or a government "
              "scheme — speak in Hindi, Punjabi, Marathi or English, and get "
              "practical advice back.",
        "hi": "अपनी फसल, खेत के मौसम या किसी सरकारी योजना के बारे में पूछिए — "
              "हिन्दी, पंजाबी, मराठी या अंग्रेज़ी में बोलिए, और काम की सलाह पाइए।",
        "pa": "ਆਪਣੀ ਫ਼ਸਲ, ਖੇਤ ਦੇ ਮੌਸਮ ਜਾਂ ਕਿਸੇ ਸਰਕਾਰੀ ਯੋਜਨਾ ਬਾਰੇ ਪੁੱਛੋ — "
              "ਹਿੰਦੀ, ਪੰਜਾਬੀ, ਮਰਾਠੀ ਜਾਂ ਅੰਗਰੇਜ਼ੀ ਵਿੱਚ ਬੋਲੋ, ਅਤੇ ਕੰਮ ਦੀ ਸਲਾਹ ਪਾਓ।",
        "mr": "तुमचे पीक, शेतातील हवामान किंवा एखाद्या सरकारी योजनेबद्दल विचारा — "
              "हिंदी, पंजाबी, मराठी किंवा इंग्रजीत बोला, आणि उपयुक्त सल्ला मिळवा.",
    },
    "hero_body_lite": {
        "en": "Type a question in English about your crop, the weather over your "
              "field, or a government scheme — and get practical advice back.",
        "hi": "अपनी फसल, खेत के मौसम या किसी सरकारी योजना के बारे में अंग्रेज़ी में "
              "सवाल लिखिए — और काम की सलाह पाइए।",
        "pa": "ਆਪਣੀ ਫ਼ਸਲ, ਖੇਤ ਦੇ ਮੌਸਮ ਜਾਂ ਕਿਸੇ ਸਰਕਾਰੀ ਯੋਜਨਾ ਬਾਰੇ ਅੰਗਰੇਜ਼ੀ ਵਿੱਚ "
              "ਸਵਾਲ ਲਿਖੋ — ਅਤੇ ਕੰਮ ਦੀ ਸਲਾਹ ਪਾਓ।",
        "mr": "तुमचे पीक, शेतातील हवामान किंवा एखाद्या सरकारी योजनेबद्दल इंग्रजीत "
              "प्रश्न लिहा — आणि उपयुक्त सल्ला मिळवा.",
    },

    # ── Ask panel ────────────────────────────────────────────────────────────
    "eyebrow_speak": {"en": "Speak", "hi": "बोलिए", "pa": "ਬੋਲੋ", "mr": "बोला"},
    "mic_note": {  # {language} = the chosen language's name
        "en": "Tap the microphone and ask in {language}.",
        "hi": "माइक दबाइए और {language} में पूछिए।",
        "pa": "ਮਾਈਕ ਦਬਾਓ ਅਤੇ {language} ਵਿੱਚ ਪੁੱਛੋ।",
        "mr": "माइक दाबा आणि {language}मध्ये विचारा.",
    },
    "eyebrow_or_type": {
        "en": "Or type", "hi": "या लिखिए (अंग्रेज़ी में)",
        "pa": "ਜਾਂ ਲਿਖੋ (ਅੰਗਰੇਜ਼ੀ ਵਿੱਚ)", "mr": "किंवा लिहा (इंग्रजीत)",
    },
    "eyebrow_question": {
        "en": "Your question", "hi": "आपका सवाल (अंग्रेज़ी में)",
        "pa": "ਤੁਹਾਡਾ ਸਵਾਲ (ਅੰਗਰੇਜ਼ੀ ਵਿੱਚ)", "mr": "तुमचा प्रश्न (इंग्रजीत)",
    },
    "lite_note": {
        "en": "Voice questions run in the full version. This lightweight demo takes "
              "typed questions in English.",
        "hi": "आवाज़ से सवाल पूरे संस्करण में पूछे जा सकते हैं। इस हल्के डेमो में "
              "सवाल अंग्रेज़ी में लिखकर पूछिए।",
        "pa": "ਆਵਾਜ਼ ਨਾਲ ਸਵਾਲ ਪੂਰੇ ਸੰਸਕਰਣ ਵਿੱਚ ਪੁੱਛੇ ਜਾ ਸਕਦੇ ਹਨ। ਇਸ ਹਲਕੇ ਡੈਮੋ ਵਿੱਚ "
              "ਸਵਾਲ ਅੰਗਰੇਜ਼ੀ ਵਿੱਚ ਲਿਖ ਕੇ ਪੁੱਛੋ।",
        "mr": "आवाजाने प्रश्न पूर्ण आवृत्तीत विचारता येतात. या हलक्या डेमोमध्ये "
              "प्रश्न इंग्रजीत लिहून विचारा.",
    },
    "text_placeholder": {
        "en": "Will it rain in Pune tomorrow? Any scheme for irrigation?",
        "hi": "अंग्रेज़ी में लिखें, जैसे: Will it rain in Pune tomorrow?",
        "pa": "ਅੰਗਰੇਜ਼ੀ ਵਿੱਚ ਲਿਖੋ, ਜਿਵੇਂ: Will it rain in Pune tomorrow?",
        "mr": "इंग्रजीत लिहा, उदा.: Will it rain in Pune tomorrow?",
    },
    "eyebrow_location": {"en": "Location", "hi": "स्थान", "pa": "ਟਿਕਾਣਾ", "mr": "ठिकाण"},
    "location_note": {
        "en": "Used to pull the live forecast over your field.",
        "hi": "आपके खेत के मौसम का ताज़ा पूर्वानुमान लाने के लिए।",
        "pa": "ਤੁਹਾਡੇ ਖੇਤ ਦੇ ਮੌਸਮ ਦੀ ਤਾਜ਼ਾ ਭਵਿੱਖਬਾਣੀ ਲਿਆਉਣ ਲਈ।",
        "mr": "तुमच्या शेतावरील हवामानाचा ताजा अंदाज आणण्यासाठी.",
    },
    "location_placeholder": {
        "en": "Nashik · Ludhiana · Varanasi",
        "hi": "अंग्रेज़ी में, जैसे: Nashik · Ludhiana",
        "pa": "ਅੰਗਰੇਜ਼ੀ ਵਿੱਚ, ਜਿਵੇਂ: Nashik · Ludhiana",
        "mr": "इंग्रजीत, उदा.: Nashik · Ludhiana",
    },
    "ask_button": {
        "en": "Ask the assistant", "hi": "सहायक से पूछिए",
        "pa": "ਸਹਾਇਕ ਨੂੰ ਪੁੱਛੋ", "mr": "सहाय्यकाला विचारा",
    },
    "eyebrow_detected": {
        "en": "Question language", "hi": "सवाल की भाषा",
        "pa": "ਸਵਾਲ ਦੀ ਭਾਸ਼ਾ", "mr": "प्रश्नाची भाषा",
    },
    "pending": {
        "en": "Awaiting your question", "hi": "आपके सवाल का इंतज़ार",
        "pa": "ਤੁਹਾਡੇ ਸਵਾਲ ਦੀ ਉਡੀਕ", "mr": "तुमच्या प्रश्नाची प्रतीक्षा",
    },
    "mode_typed": {"en": "typed", "hi": "लिखकर", "pa": "ਲਿਖ ਕੇ", "mr": "लिहून"},
    "mode_voice": {"en": "voice", "hi": "आवाज़ से", "pa": "ਆਵਾਜ਼ ਨਾਲ", "mr": "आवाजाने"},
    "eyebrow_try": {
        "en": "Try one", "hi": "एक आज़माइए", "pa": "ਇੱਕ ਅਜ਼ਮਾਓ", "mr": "एक वापरून पाहा",
    },

    # ── Answer panel ─────────────────────────────────────────────────────────
    "eyebrow_response": {"en": "Response", "hi": "जवाब", "pa": "ਜਵਾਬ", "mr": "उत्तर"},
    "answer_note": {
        "en": "Advice is shown and spoken in English.",
        "hi": "सलाह अंग्रेज़ी में दिखाई और सुनाई जाती है।",
        "pa": "ਸਲਾਹ ਅੰਗਰੇਜ਼ੀ ਵਿੱਚ ਦਿਖਾਈ ਅਤੇ ਸੁਣਾਈ ਜਾਂਦੀ ਹੈ।",
        "mr": "सल्ला इंग्रजीत दाखवला आणि ऐकवला जातो.",
    },
    "answer_placeholder": {
        "en": "Your advice will appear here.", "hi": "आपकी सलाह यहाँ दिखेगी।",
        "pa": "ਤੁਹਾਡੀ ਸਲਾਹ ਇੱਥੇ ਦਿਖਾਈ ਦੇਵੇਗੀ।", "mr": "तुमचा सल्ला येथे दिसेल.",
    },
    "audio_label": {
        "en": "Spoken reply", "hi": "सुनाई गई सलाह",
        "pa": "ਸੁਣਾਈ ਗਈ ਸਲਾਹ", "mr": "ऐकवलेला सल्ला",
    },
    "eyebrow_say_aloud": {
        "en": "Or say it aloud", "hi": "या बोलकर पूछिए",
        "pa": "ਜਾਂ ਬੋਲ ਕੇ ਪੁੱਛੋ", "mr": "किंवा बोलून विचारा",
    },
    "tools_idle": {"en": "Standing by", "hi": "तैयार", "pa": "ਤਿਆਰ", "mr": "तयार"},
    "tools_used": {  # {n} = number of sources used
        "en": "{n} of 3 sources consulted", "hi": "3 में से {n} स्रोत देखे गए",
        "pa": "3 ਵਿੱਚੋਂ {n} ਸਰੋਤ ਵੇਖੇ ਗਏ", "mr": "3 पैकी {n} स्रोत तपासले",
    },
    "tools_none": {
        "en": "Answered without external sources", "hi": "बाहरी स्रोतों के बिना जवाब दिया",
        "pa": "ਬਾਹਰੀ ਸਰੋਤਾਂ ਤੋਂ ਬਿਨਾਂ ਜਵਾਬ ਦਿੱਤਾ", "mr": "बाह्य स्रोतांशिवाय उत्तर दिले",
    },
    "tool_crop": {"en": "Crop knowledge", "hi": "फसल जानकारी", "pa": "ਫ਼ਸਲ ਜਾਣਕਾਰੀ", "mr": "पीक माहिती"},
    "tool_weather": {"en": "Weather", "hi": "मौसम", "pa": "ਮੌਸਮ", "mr": "हवामान"},
    "tool_scheme": {"en": "Govt scheme", "hi": "सरकारी योजना", "pa": "ਸਰਕਾਰੀ ਯੋਜਨਾ", "mr": "सरकारी योजना"},
    "chip_used": {"en": "used", "hi": "उपयोग हुआ", "pa": "ਵਰਤਿਆ", "mr": "वापरले"},
    "chip_idle": {"en": "idle", "hi": "उपयोग नहीं", "pa": "ਵਰਤਿਆ ਨਹੀਂ", "mr": "वापरले नाही"},

    # ── Diagnostics & footer ─────────────────────────────────────────────────
    "diag": {
        "en": "Transcript & pipeline", "hi": "प्रतिलेख और प्रक्रिया",
        "pa": "ਲਿਖਤ ਅਤੇ ਪ੍ਰਕਿਰਿਆ", "mr": "प्रतिलेख आणि प्रक्रिया",
    },
    "heard_label": {"en": "Heard", "hi": "सुना गया", "pa": "ਸੁਣਿਆ ਗਿਆ", "mr": "ऐकलेले"},
    "heard_placeholder": {
        "en": "Your words, as transcribed.", "hi": "आपके शब्द, जैसे लिखे गए।",
        "pa": "ਤੁਹਾਡੇ ਸ਼ਬਦ, ਜਿਵੇਂ ਲਿਖੇ ਗਏ।", "mr": "तुमचे शब्द, जसे लिहिले गेले.",
    },
    "english_label": {
        "en": "English translation", "hi": "अंग्रेज़ी अनुवाद",
        "pa": "ਅੰਗਰੇਜ਼ੀ ਅਨੁਵਾਦ", "mr": "इंग्रजी भाषांतर",
    },
    "english_placeholder": {
        "en": "The English the agent reasoned over.",
        "hi": "वह अंग्रेज़ी पाठ जिस पर सहायक ने विचार किया।",
        "pa": "ਉਹ ਅੰਗਰੇਜ਼ੀ ਪਾਠ ਜਿਸ ਉੱਤੇ ਸਹਾਇਕ ਨੇ ਵਿਚਾਰ ਕੀਤਾ।",
        "mr": "सहाय्यकाने ज्या इंग्रजी मजकुरावर विचार केला तो.",
    },
    "intent_label": {"en": "Intent", "hi": "सवाल का प्रकार", "pa": "ਸਵਾਲ ਦੀ ਕਿਸਮ", "mr": "प्रश्नाचा प्रकार"},
    "trace_label": {"en": "Trace", "hi": "प्रक्रिया लॉग", "pa": "ਪ੍ਰਕਿਰਿਆ ਲੌਗ", "mr": "प्रक्रिया लॉग"},
    "footer_left": {
        "en": "Built for Indian farmers", "hi": "भारतीय किसानों के लिए बनाया गया",
        "pa": "ਭਾਰਤੀ ਕਿਸਾਨਾਂ ਲਈ ਬਣਾਇਆ ਗਿਆ", "mr": "भारतीय शेतकऱ्यांसाठी बनवले",
    },

    # ── Messages & errors ────────────────────────────────────────────────────
    "err_no_input": {
        "en": "Type a question above, or tap the microphone and speak.",
        "hi": "ऊपर सवाल लिखिए, या माइक दबाकर बोलिए।",
        "pa": "ਉੱਪਰ ਸਵਾਲ ਲਿਖੋ, ਜਾਂ ਮਾਈਕ ਦਬਾ ਕੇ ਬੋਲੋ।",
        "mr": "वर प्रश्न लिहा, किंवा माइक दाबून बोला.",
    },
    "err_no_input_lite": {
        "en": "Type a question above.", "hi": "ऊपर सवाल लिखिए।",
        "pa": "ਉੱਪਰ ਸਵਾਲ ਲਿਖੋ।", "mr": "वर प्रश्न लिहा.",
    },
    "err_stt": {  # {err} = technical error text
        "en": "Speech recognition failed: {err}",
        "hi": "आवाज़ पहचानने में दिक्कत हुई: {err}",
        "pa": "ਆਵਾਜ਼ ਪਛਾਣਨ ਵਿੱਚ ਦਿੱਕਤ ਆਈ: {err}",
        "mr": "आवाज ओळखण्यात अडचण आली: {err}",
    },
    "err_type_english": {
        "en": "Please type in English — or choose your language above and ask with the microphone.",
        "hi": "कृपया अंग्रेज़ी में लिखिए — या ऊपर अपनी भाषा चुनकर माइक से पूछिए।",
        "pa": "ਕਿਰਪਾ ਕਰਕੇ ਅੰਗਰੇਜ਼ੀ ਵਿੱਚ ਲਿਖੋ — ਜਾਂ ਉੱਪਰ ਆਪਣੀ ਭਾਸ਼ਾ ਚੁਣ ਕੇ ਮਾਈਕ ਨਾਲ ਪੁੱਛੋ।",
        "mr": "कृपया इंग्रजीत लिहा — किंवा वर तुमची भाषा निवडून माइकने विचारा.",
    },
    "err_type_english_lite": {
        "en": "Please type your question in English.",
        "hi": "कृपया अपना सवाल अंग्रेज़ी में लिखिए।",
        "pa": "ਕਿਰਪਾ ਕਰਕੇ ਆਪਣਾ ਸਵਾਲ ਅੰਗਰੇਜ਼ੀ ਵਿੱਚ ਲਿਖੋ।",
        "mr": "कृपया तुमचा प्रश्न इंग्रजीत लिहा.",
    },
}

# Spoken-question prompts shown under "Or say it aloud", per chosen language.
SPOKEN_EXAMPLES = {
    "en": [
        "My onion crop is 45 days old — what care does it need?",
        "Will it rain in Ludhiana this week?",
        "What documents do I need for a Kisan Credit Card?",
        "There are insects on my cotton plants.",
    ],
    "hi": [
        "मेरी गेहूं 40 दिन की है, क्या खाद डालूं?",
        "पुणे में कल बारिश होगी क्या? धान की सिंचाई करूं?",
        "PM किसान योजना के लिए कैसे आवेदन करें?",
        "मेरे टमाटर की पत्तियां पीली हो रही हैं, क्या करूं?",
    ],
    "pa": [
        "ਮੇਰੀ ਕਣਕ 40 ਦਿਨ ਦੀ ਹੈ, ਕਿਹੜੀ ਖਾਦ ਪਾਵਾਂ?",
        "ਲੁਧਿਆਣਾ ਵਿੱਚ ਕੱਲ੍ਹ ਮੀਂਹ ਪਵੇਗਾ ਕੀ?",
        "ਕਿਸਾਨ ਕ੍ਰੈਡਿਟ ਕਾਰਡ ਲਈ ਕਿਵੇਂ ਅਪਲਾਈ ਕਰਨਾ ਹੈ?",
        "ਮੇਰੇ ਝੋਨੇ ਵਿੱਚ ਕੀੜੇ ਲੱਗ ਗਏ ਹਨ।",
    ],
    "mr": [
        "माझ्या कापसाला 40 दिवस झाले, कोणते खत द्यावे?",
        "नाशिकमध्ये उद्या पाऊस येईल का?",
        "पीएम किसान योजनेसाठी कोणती कागदपत्रे लागतात?",
        "माझ्या कांद्याची पाने पिवळी पडत आहेत.",
    ],
}


def normalize_lang(lang: str | None) -> str:
    return lang if lang in LANG_CODES else DEFAULT_LANG


def t(key: str, lang: str | None, **kwargs) -> str:
    """Translated string for `key`, falling back to English."""
    entry = STRINGS[key]
    text = entry.get(normalize_lang(lang)) or entry[DEFAULT_LANG]
    return text.format(**kwargs) if kwargs else text


def lang_name(code: str, ui_lang: str | None) -> str:
    """Name of language `code`, written in the UI language."""
    names = LANG_NAMES[normalize_lang(ui_lang)]
    return names.get(code, names[DEFAULT_LANG])
