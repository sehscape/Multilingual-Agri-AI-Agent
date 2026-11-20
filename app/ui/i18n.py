"""UI translations — every piece of on-screen text in English, Hindi, Punjabi, Marathi.

The language picked on the page drives the whole interface: labels, buttons,
instructions, placeholders, tool status, error messages and voice prompts.
The farmer's question and the agent's answer are content, not UI; see
app/ui/gradio_app.py for how voice questions in each language are handled.

Keep every key present in all four languages — scripts/test_i18n.py checks it.
"""
from __future__ import annotations

from app import knowledge

# Picker labels — exactly as shown on the page — and their language codes.
# Each language is written in its own script first, so a farmer finds theirs
# at a glance. (Flag emoji were dropped: Windows shows them as "GB" / "IN".)
LANG_CHOICES = [
    ("English", "en"),
    ("हिंदी Hindi", "hi"),
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
    "eyebrow_location": {
        "en": "Your village", "hi": "आपका गाँव", "pa": "ਤੁਹਾਡਾ ਪਿੰਡ", "mr": "तुमचे गाव",
    },
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
        "en": "Try asking", "hi": "ऐसे पूछ सकते हैं", "pa": "ਇੰਝ ਪੁੱਛ ਸਕਦੇ ਹੋ",
        "mr": "असे विचारू शकता",
    },

    # ── Answer panel ─────────────────────────────────────────────────────────
    "eyebrow_response": {"en": "Answer", "hi": "जवाब", "pa": "ਜਵਾਬ", "mr": "उत्तर"},
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
        "en": "Listen to the answer", "hi": "जवाब सुनिए",
        "pa": "ਜਵਾਬ ਸੁਣੋ", "mr": "उत्तर ऐका",
    },
    "eyebrow_say_aloud": {
        "en": "Or say it aloud", "hi": "या बोलकर पूछिए",
        "pa": "ਜਾਂ ਬੋਲ ਕੇ ਪੁੱਛੋ", "mr": "किंवा बोलून विचारा",
    },
    "tools_idle": {
        "en": "Answers come only from these sources",
        "hi": "जवाब सिर्फ़ इन्हीं स्रोतों से आते हैं",
        "pa": "ਜਵਾਬ ਸਿਰਫ਼ ਇਨ੍ਹਾਂ ਸਰੋਤਾਂ ਤੋਂ ਆਉਂਦੇ ਹਨ",
        "mr": "उत्तरे फक्त या स्रोतांमधूनच येतात",
    },
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
        "en": "How this answer was made", "hi": "यह जवाब कैसे बना",
        "pa": "ਇਹ ਜਵਾਬ ਕਿਵੇਂ ਬਣਿਆ", "mr": "हे उत्तर कसे तयार झाले",
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

    # ══ Voice + regional build (Groq, or IndicTrans2) ════════════════════════
    # Used instead of the "in English" wording above when the app can hear and
    # answer every language.
    "hero_body_voice": {
        "en": "Tap the microphone and ask about your crop, the weather over your field, "
              "or a government scheme — in Hindi, Punjabi, Marathi or English. The answer "
              "is spoken back in your language.",
        "hi": "माइक दबाइए और अपनी फसल, खेत के मौसम या किसी सरकारी योजना के बारे में "
              "पूछिए — हिन्दी, पंजाबी, मराठी या अंग्रेज़ी में। जवाब आपकी भाषा में बोलकर "
              "सुनाया जाएगा।",
        "pa": "ਮਾਈਕ ਦਬਾਓ ਅਤੇ ਆਪਣੀ ਫ਼ਸਲ, ਖੇਤ ਦੇ ਮੌਸਮ ਜਾਂ ਕਿਸੇ ਸਰਕਾਰੀ ਸਕੀਮ ਬਾਰੇ ਪੁੱਛੋ — "
              "ਹਿੰਦੀ, ਪੰਜਾਬੀ, ਮਰਾਠੀ ਜਾਂ ਅੰਗਰੇਜ਼ੀ ਵਿੱਚ। ਜਵਾਬ ਤੁਹਾਡੀ ਭਾਸ਼ਾ ਵਿੱਚ ਬੋਲ ਕੇ "
              "ਸੁਣਾਇਆ ਜਾਵੇਗਾ।",
        "mr": "माइक दाबा आणि तुमचे पीक, शेतातील हवामान किंवा एखाद्या सरकारी योजनेबद्दल "
              "विचारा — हिंदी, पंजाबी, मराठी किंवा इंग्रजीत. उत्तर तुमच्या भाषेत बोलून "
              "ऐकवले जाईल.",
    },
    "mic_note_auto": {  # {language} = the chosen language's name
        "en": "Tap the microphone, ask in {language}, then tap stop. The answer plays by itself.",
        "hi": "माइक दबाइए, {language} में पूछिए, फिर रोकिए। जवाब अपने-आप सुनाई देगा।",
        "pa": "ਮਾਈਕ ਦਬਾਓ, {language} ਵਿੱਚ ਪੁੱਛੋ, ਫਿਰ ਰੋਕੋ। ਜਵਾਬ ਆਪਣੇ-ਆਪ ਸੁਣਾਈ ਦੇਵੇਗਾ।",
        "mr": "माइक दाबा, {language}मध्ये विचारा, मग थांबवा. उत्तर आपोआप ऐकू येईल.",
    },
    "eyebrow_or_type_any": {"en": "Or type", "hi": "या लिखिए", "pa": "ਜਾਂ ਲਿਖੋ", "mr": "किंवा लिहा"},
    "text_placeholder_native": {
        "en": "Will it rain in Pune tomorrow? Any scheme for irrigation?",
        "hi": "यहाँ लिखिए, जैसे: क्या कल पुणे में बारिश होगी?",
        "pa": "ਇੱਥੇ ਲਿਖੋ, ਜਿਵੇਂ: ਕੀ ਕੱਲ੍ਹ ਲੁਧਿਆਣਾ ਵਿੱਚ ਮੀਂਹ ਪਵੇਗਾ?",
        "mr": "येथे लिहा, उदा.: उद्या नाशिकमध्ये पाऊस येईल का?",
    },
    "location_note_voice": {
        "en": "Say your village in the question, type it here, or tap 📍 once — it is remembered.",
        "hi": "सवाल में अपने गाँव का नाम बोलिए, यहाँ लिखिए, या एक बार 📍 दबाइए — याद रखा जाएगा।",
        "pa": "ਸਵਾਲ ਵਿੱਚ ਆਪਣੇ ਪਿੰਡ ਦਾ ਨਾਮ ਬੋਲੋ, ਇੱਥੇ ਲਿਖੋ, ਜਾਂ ਇੱਕ ਵਾਰ 📍 ਦਬਾਓ — ਯਾਦ ਰੱਖਿਆ ਜਾਵੇਗਾ।",
        "mr": "प्रश्नात तुमच्या गावाचे नाव सांगा, येथे लिहा, किंवा एकदा 📍 दाबा — लक्षात ठेवले जाईल.",
    },
    "location_placeholder_native": {
        "en": "Your village or town", "hi": "आपका गाँव या शहर",
        "pa": "ਤੁਹਾਡਾ ਪਿੰਡ ਜਾਂ ਸ਼ਹਿਰ", "mr": "तुमचे गाव किंवा शहर",
    },
    "gps_button": {
        "en": "📍 Use my location", "hi": "📍 मेरी लोकेशन लें",
        "pa": "📍 ਮੇਰੀ ਲੋਕੇਸ਼ਨ ਲਓ", "mr": "📍 माझे ठिकाण वापरा",
    },
    "your_location": {
        "en": "your location", "hi": "आपकी जगह", "pa": "ਤੁਹਾਡੀ ਥਾਂ", "mr": "तुमचे ठिकाण",
    },
    "eyebrow_can_help": {
        "en": "What I can help with", "hi": "मैं किसमें मदद कर सकता हूँ",
        "pa": "ਮੈਂ ਕਿਸ ਵਿੱਚ ਮਦਦ ਕਰ ਸਕਦਾ ਹਾਂ", "mr": "मी कशात मदत करू शकतो",
    },
    "help_crop": {  # {count} = how many crops the guide covers
        "en": "🌾 Crop care — fertilizer, water, pests and disease for {count} crops: wheat, "
              "rice, cotton, sugarcane, soybean, chickpea, potato, banana and more",
        "hi": "🌾 फसल की देखभाल — {count} फसलों के लिए खाद, पानी, कीड़े और रोग: गेहूं, धान, "
              "कपास, गन्ना, सोयाबीन, चना, आलू, केला और भी",
        "pa": "🌾 ਫ਼ਸਲ ਦੀ ਸੰਭਾਲ — {count} ਫ਼ਸਲਾਂ ਲਈ ਖਾਦ, ਪਾਣੀ, ਕੀੜੇ ਅਤੇ ਰੋਗ: ਕਣਕ, ਝੋਨਾ, "
              "ਕਪਾਹ, ਗੰਨਾ, ਸਰ੍ਹੋਂ, ਆਲੂ, ਮੱਕੀ, ਮੂੰਗੀ ਅਤੇ ਹੋਰ",
        "mr": "🌾 पिकाची काळजी — {count} पिकांसाठी खत, पाणी, कीड आणि रोग: ऊस, कापूस, "
              "सोयाबीन, कांदा, तूर, हरभरा, ज्वारी, केळी आणि इतर",
    },
    "help_weather": {
        "en": "🌦 Weather — rain, heat and wind for your village, for the next 3 days",
        "hi": "🌦 मौसम — आपके गाँव में बारिश, गर्मी और हवा, अगले 3 दिन",
        "pa": "🌦 ਮੌਸਮ — ਤੁਹਾਡੇ ਪਿੰਡ ਵਿੱਚ ਮੀਂਹ, ਗਰਮੀ ਅਤੇ ਹਵਾ, ਅਗਲੇ 3 ਦਿਨ",
        "mr": "🌦 हवामान — तुमच्या गावातील पाऊस, उष्णता आणि वारा, पुढील 3 दिवस",
    },
    "help_scheme": {
        "en": "🏛 Government schemes — PM-KISAN, crop insurance, Kisan Credit Card, solar "
              "pumps (PM-KUSUM), drip subsidy, farmer pension and more",
        "hi": "🏛 सरकारी योजनाएँ — पीएम किसान, फसल बीमा, किसान क्रेडिट कार्ड, सोलर पंप "
              "(कुसुम), ड्रिप सब्सिडी, किसान पेंशन और भी",
        "pa": "🏛 ਸਰਕਾਰੀ ਸਕੀਮਾਂ — ਪੀਐਮ ਕਿਸਾਨ, ਫ਼ਸਲ ਬੀਮਾ, ਕਿਸਾਨ ਕ੍ਰੈਡਿਟ ਕਾਰਡ, ਸੋਲਰ ਪੰਪ "
              "(ਕੁਸੁਮ), ਪਰਾਲੀ ਮਸ਼ੀਨ ਸਬਸਿਡੀ ਅਤੇ ਹੋਰ",
        "mr": "🏛 सरकारी योजना — पीएम किसान, नमो शेतकरी, पीक विमा, किसान क्रेडिट कार्ड, "
              "सौर पंप (कुसुम), ठिबक अनुदान आणि इतर",
    },
    "voice_question": {
        "en": "Voice question…", "hi": "आवाज़ में सवाल…",
        "pa": "ਆਵਾਜ਼ ਵਿੱਚ ਸਵਾਲ…", "mr": "आवाजातील प्रश्न…",
    },
    "new_chat": {
        "en": "↺ New conversation", "hi": "↺ नई बातचीत",
        "pa": "↺ ਨਵੀਂ ਗੱਲਬਾਤ", "mr": "↺ नवीन संभाषण",
    },
    # The big microphone button (shown through CSS, see gradio_app._mic_css)
    "mic_tap": {
        "en": "Tap to speak", "hi": "बोलने के लिए दबाएँ",
        "pa": "ਬੋਲਣ ਲਈ ਦਬਾਓ", "mr": "बोलण्यासाठी दाबा",
    },
    "mic_stop": {
        "en": "Tap to stop", "hi": "रोकने के लिए दबाएँ",
        "pa": "ਰੋਕਣ ਲਈ ਦਬਾਓ", "mr": "थांबवण्यासाठी दाबा",
    },
    "kvk_note": {
        "en": "This advice is general. For exact doses, check with your nearest "
              "Krishi Vigyan Kendra (KVK).",
        "hi": "यह सलाह सामान्य है। सही मात्रा के लिए अपने नज़दीकी कृषि विज्ञान केंद्र "
              "(KVK) से पूछें।",
        "pa": "ਇਹ ਸਲਾਹ ਆਮ ਹੈ। ਸਹੀ ਮਾਤਰਾ ਲਈ ਆਪਣੇ ਨੇੜਲੇ ਕ੍ਰਿਸ਼ੀ ਵਿਗਿਆਨ ਕੇਂਦਰ (KVK) "
              "ਤੋਂ ਪੁੱਛੋ।",
        "mr": "हा सल्ला सर्वसाधारण आहे. नेमक्या मात्रेसाठी जवळच्या कृषी विज्ञान "
              "केंद्राला (KVK) विचारा.",
    },

    # ── Questions back to the farmer (shown and spoken) ──────────────────────
    "ask_crop": {
        "en": "Which crop is this about? Please tell me its name — for example wheat, "
              "cotton, sugarcane or soybean.",
        "hi": "यह किस फसल के बारे में है? कृपया उसका नाम बताइए — जैसे गेहूं, धान, गन्ना "
              "या चना।",
        "pa": "ਇਹ ਕਿਹੜੀ ਫ਼ਸਲ ਬਾਰੇ ਹੈ? ਕਿਰਪਾ ਕਰਕੇ ਉਸਦਾ ਨਾਮ ਦੱਸੋ — ਜਿਵੇਂ ਕਣਕ, ਝੋਨਾ, "
              "ਕਪਾਹ ਜਾਂ ਗੰਨਾ।",
        "mr": "हे कोणत्या पिकाबद्दल आहे? कृपया त्याचे नाव सांगा — उदा. ऊस, कापूस, "
              "सोयाबीन किंवा कांदा.",
    },
    "ask_age": {  # {crop} = crop name in the chosen language
        "en": "How many days old is your {crop} crop? Please tell me, for example: “40 days”.",
        "hi": "आपकी {crop} की फसल कितने दिन की है? कृपया बताइए, जैसे: “40 दिन”।",
        "pa": "ਤੁਹਾਡੀ {crop} ਦੀ ਫ਼ਸਲ ਕਿੰਨੇ ਦਿਨਾਂ ਦੀ ਹੈ? ਕਿਰਪਾ ਕਰਕੇ ਦੱਸੋ, ਜਿਵੇਂ: “40 ਦਿਨ”।",
        "mr": "तुमचे पीक ({crop}) किती दिवसांचे आहे? कृपया सांगा, उदा.: “40 दिवस”.",
    },
    "ask_age_check": {  # {crop} {days} {total}
        "en": "Your {crop} crop is usually ready in about {total} days, but you said {days} "
              "days. Please check the crop's age and tell me again.",
        "hi": "{crop} की फसल आमतौर पर लगभग {total} दिन में तैयार हो जाती है, पर आपने "
              "{days} दिन बताए। कृपया फसल की उम्र जाँचकर फिर से बताइए।",
        "pa": "{crop} ਦੀ ਫ਼ਸਲ ਆਮ ਤੌਰ 'ਤੇ ਲਗਭਗ {total} ਦਿਨਾਂ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਂਦੀ ਹੈ, ਪਰ ਤੁਸੀਂ "
              "{days} ਦਿਨ ਦੱਸੇ। ਕਿਰਪਾ ਕਰਕੇ ਫ਼ਸਲ ਦੀ ਉਮਰ ਜਾਂਚ ਕੇ ਦੁਬਾਰਾ ਦੱਸੋ।",
        "mr": "{crop} पीक साधारणपणे सुमारे {total} दिवसांत तयार होते, पण तुम्ही {days} "
              "दिवस सांगितले. कृपया पिकाचे वय तपासून पुन्हा सांगा.",
    },
    "ask_location": {
        "en": "Which village or town are you in? Say its name, or tap “📍 Use my location”.",
        "hi": "आप किस गाँव या शहर में हैं? उसका नाम बोलिए, या “📍 मेरी लोकेशन लें” दबाइए।",
        "pa": "ਤੁਸੀਂ ਕਿਹੜੇ ਪਿੰਡ ਜਾਂ ਸ਼ਹਿਰ ਵਿੱਚ ਹੋ? ਉਸਦਾ ਨਾਮ ਬੋਲੋ, ਜਾਂ “📍 ਮੇਰੀ ਲੋਕੇਸ਼ਨ ਲਓ” ਦਬਾਓ।",
        "mr": "तुम्ही कोणत्या गावात किंवा शहरात आहात? त्याचे नाव सांगा, किंवा "
              "“📍 माझे ठिकाण वापरा” दाबा.",
    },
    "ask_place_not_found": {  # {place}
        "en": "I could not find “{place}”. Please say the name of a nearby big town or your district.",
        "hi": "मुझे “{place}” नहीं मिला। कृपया पास के किसी बड़े शहर या अपने ज़िले का नाम बताइए।",
        "pa": "ਮੈਨੂੰ “{place}” ਨਹੀਂ ਮਿਲਿਆ। ਕਿਰਪਾ ਕਰਕੇ ਨੇੜੇ ਦੇ ਕਿਸੇ ਵੱਡੇ ਸ਼ਹਿਰ ਜਾਂ ਆਪਣੇ "
              "ਜ਼ਿਲ੍ਹੇ ਦਾ ਨਾਮ ਦੱਸੋ।",
        "mr": "मला “{place}” सापडले नाही. कृपया जवळच्या मोठ्या शहराचे किंवा तुमच्या "
              "जिल्ह्याचे नाव सांगा.",
    },
    "ask_unsupported_crop": {  # {crop} = the crop as the farmer said it
        "en": "I don't have advice for {crop} yet. I can help with these crops: {crops}.",
        "hi": "अभी मेरे पास {crop} के बारे में जानकारी नहीं है। मैं इन फसलों में मदद कर "
              "सकता हूँ: {crops}।",
        "pa": "ਅਜੇ ਮੇਰੇ ਕੋਲ {crop} ਬਾਰੇ ਜਾਣਕਾਰੀ ਨਹੀਂ ਹੈ। ਮੈਂ ਇਨ੍ਹਾਂ ਫ਼ਸਲਾਂ ਵਿੱਚ ਮਦਦ ਕਰ "
              "ਸਕਦਾ ਹਾਂ: {crops}।",
        "mr": "सध्या माझ्याकडे {crop} बद्दल माहिती नाही. मी या पिकांबाबत मदत करू "
              "शकतो: {crops}.",
    },
    "ask_scheme_unknown": {
        "en": "I don't have details of that scheme. I can tell you about {schemes}.",
        "hi": "उस योजना की जानकारी मेरे पास नहीं है। मैं इनके बारे में बता सकता हूँ: "
              "{schemes}।",
        "pa": "ਉਸ ਸਕੀਮ ਦੀ ਜਾਣਕਾਰੀ ਮੇਰੇ ਕੋਲ ਨਹੀਂ ਹੈ। ਮੈਂ ਇਨ੍ਹਾਂ ਬਾਰੇ ਦੱਸ ਸਕਦਾ ਹਾਂ: "
              "{schemes}।",
        "mr": "त्या योजनेची माहिती माझ्याकडे नाही. मी यांबद्दल सांगू शकतो: {schemes}.",
    },
    "ask_offtopic": {  # {example} = a sample question in the chosen language
        "en": "I can help only with farming: crop care, the weather for your field, and "
              "government schemes for farmers. For example, ask: “{example}”",
        "hi": "मैं सिर्फ़ खेती में मदद कर सकता हूँ: फसल की देखभाल, खेत का मौसम और किसानों "
              "की सरकारी योजनाएँ। जैसे पूछिए: “{example}”",
        "pa": "ਮੈਂ ਸਿਰਫ਼ ਖੇਤੀ ਵਿੱਚ ਮਦਦ ਕਰ ਸਕਦਾ ਹਾਂ: ਫ਼ਸਲ ਦੀ ਸੰਭਾਲ, ਖੇਤ ਦਾ ਮੌਸਮ ਅਤੇ "
              "ਕਿਸਾਨਾਂ ਲਈ ਸਰਕਾਰੀ ਸਕੀਮਾਂ। ਜਿਵੇਂ ਪੁੱਛੋ: “{example}”",
        "mr": "मी फक्त शेतीविषयी मदत करू शकतो: पिकाची काळजी, शेतातील हवामान आणि "
              "शेतकऱ्यांसाठी सरकारी योजना. उदा. असे विचारा: “{example}”",
    },
    "ask_unclear": {  # {example}
        "en": "Sorry, I did not understand. Please ask again about your crop, the weather, "
              "or a government scheme. For example: “{example}”",
        "hi": "माफ़ कीजिए, मैं समझ नहीं पाया। कृपया अपनी फसल, मौसम या किसी सरकारी योजना "
              "के बारे में फिर से पूछिए। जैसे: “{example}”",
        "pa": "ਮਾਫ਼ ਕਰਨਾ, ਮੈਂ ਸਮਝ ਨਹੀਂ ਸਕਿਆ। ਕਿਰਪਾ ਕਰਕੇ ਆਪਣੀ ਫ਼ਸਲ, ਮੌਸਮ ਜਾਂ ਕਿਸੇ "
              "ਸਰਕਾਰੀ ਸਕੀਮ ਬਾਰੇ ਦੁਬਾਰਾ ਪੁੱਛੋ। ਜਿਵੇਂ: “{example}”",
        "mr": "माफ करा, मला समजले नाही. कृपया तुमचे पीक, हवामान किंवा एखाद्या सरकारी "
              "योजनेबद्दल पुन्हा विचारा. उदा.: “{example}”",
    },
    "msg_greeting": {  # {example}
        "en": "Namaste! Ask me about your crop, the weather, or a government scheme. "
              "For example: “{example}”",
        "hi": "नमस्ते! मुझसे अपनी फसल, मौसम या किसी सरकारी योजना के बारे में पूछिए। "
              "जैसे: “{example}”",
        "pa": "ਸਤ ਸ੍ਰੀ ਅਕਾਲ! ਮੈਨੂੰ ਆਪਣੀ ਫ਼ਸਲ, ਮੌਸਮ ਜਾਂ ਕਿਸੇ ਸਰਕਾਰੀ ਸਕੀਮ ਬਾਰੇ ਪੁੱਛੋ। "
              "ਜਿਵੇਂ: “{example}”",
        "mr": "नमस्कार! मला तुमचे पीक, हवामान किंवा एखाद्या सरकारी योजनेबद्दल विचारा. "
              "उदा.: “{example}”",
    },
    "note_age_for_exact": {  # {crop}
        "en": "For exact fertilizer and water advice, tell me how many days old your "
              "{crop} crop is.",
        "hi": "खाद और पानी की सही सलाह के लिए बताइए कि आपकी {crop} की फसल कितने दिन की है।",
        "pa": "ਖਾਦ ਅਤੇ ਪਾਣੀ ਦੀ ਸਹੀ ਸਲਾਹ ਲਈ ਦੱਸੋ ਕਿ ਤੁਹਾਡੀ {crop} ਦੀ ਫ਼ਸਲ ਕਿੰਨੇ ਦਿਨਾਂ ਦੀ ਹੈ।",
        "mr": "खत आणि पाण्याच्या अचूक सल्ल्यासाठी तुमचे पीक ({crop}) किती दिवसांचे आहे "
              "ते सांगा.",
    },
    "note_weather_down": {
        "en": "The weather service is not responding right now. Please ask about the "
              "weather again in a few minutes.",
        "hi": "मौसम सेवा अभी जवाब नहीं दे रही है। कृपया थोड़ी देर बाद मौसम के बारे में फिर पूछिए।",
        "pa": "ਮੌਸਮ ਸੇਵਾ ਇਸ ਵੇਲੇ ਜਵਾਬ ਨਹੀਂ ਦੇ ਰਹੀ। ਕਿਰਪਾ ਕਰਕੇ ਥੋੜ੍ਹੀ ਦੇਰ ਬਾਅਦ ਮੌਸਮ "
              "ਬਾਰੇ ਦੁਬਾਰਾ ਪੁੱਛੋ।",
        "mr": "हवामान सेवा सध्या प्रतिसाद देत नाही. कृपया थोड्या वेळाने हवामानाबद्दल "
              "पुन्हा विचारा.",
    },

    # ── Voice and service problems (shown and spoken) ────────────────────────
    "err_no_speech": {
        "en": "I could not hear you. Tap the microphone, speak clearly close to the phone, "
              "then tap stop.",
        "hi": "मुझे आपकी आवाज़ सुनाई नहीं दी। माइक दबाइए, फ़ोन के पास साफ़ बोलिए, फिर रोकिए।",
        "pa": "ਮੈਨੂੰ ਤੁਹਾਡੀ ਆਵਾਜ਼ ਸੁਣਾਈ ਨਹੀਂ ਦਿੱਤੀ। ਮਾਈਕ ਦਬਾਓ, ਫ਼ੋਨ ਦੇ ਨੇੜੇ ਸਾਫ਼ ਬੋਲੋ, "
              "ਫਿਰ ਰੋਕੋ।",
        "mr": "मला तुमचा आवाज ऐकू आला नाही. माइक दाबा, फोनजवळ स्पष्ट बोला, मग थांबवा.",
    },
    "err_busy": {
        "en": "Many farmers are asking right now. Please wait one minute and ask again.",
        "hi": "अभी बहुत किसान सवाल पूछ रहे हैं। कृपया एक मिनट रुककर फिर पूछिए।",
        "pa": "ਇਸ ਵੇਲੇ ਬਹੁਤ ਕਿਸਾਨ ਸਵਾਲ ਪੁੱਛ ਰਹੇ ਹਨ। ਕਿਰਪਾ ਕਰਕੇ ਇੱਕ ਮਿੰਟ ਰੁਕ ਕੇ ਦੁਬਾਰਾ ਪੁੱਛੋ।",
        "mr": "सध्या बरेच शेतकरी प्रश्न विचारत आहेत. कृपया एक मिनिट थांबून पुन्हा विचारा.",
    },
    "err_service": {
        "en": "The voice service is not working right now. Please try again in a few minutes.",
        "hi": "आवाज़ सेवा अभी काम नहीं कर रही है। कृपया कुछ मिनट बाद फिर कोशिश कीजिए।",
        "pa": "ਆਵਾਜ਼ ਸੇਵਾ ਇਸ ਵੇਲੇ ਕੰਮ ਨਹੀਂ ਕਰ ਰਹੀ। ਕਿਰਪਾ ਕਰਕੇ ਕੁਝ ਮਿੰਟਾਂ ਬਾਅਦ ਦੁਬਾਰਾ "
              "ਕੋਸ਼ਿਸ਼ ਕਰੋ।",
        "mr": "आवाज सेवा सध्या काम करत नाही. कृपया काही मिनिटांनी पुन्हा प्रयत्न करा.",
    },
    "err_too_long": {
        "en": "That recording is too long. Please ask in under one minute.",
        "hi": "रिकॉर्डिंग बहुत लंबी है। कृपया एक मिनट से कम में पूछिए।",
        "pa": "ਰਿਕਾਰਡਿੰਗ ਬਹੁਤ ਲੰਮੀ ਹੈ। ਕਿਰਪਾ ਕਰਕੇ ਇੱਕ ਮਿੰਟ ਤੋਂ ਘੱਟ ਵਿੱਚ ਪੁੱਛੋ।",
        "mr": "रेकॉर्डिंग खूप लांब आहे. कृपया एका मिनिटापेक्षा कमी वेळात विचारा.",
    },
    "note_english_fallback": {  # {language}
        "en": "I could not prepare the answer in {language} just now, so here it is in English.",
        "hi": "अभी {language} में जवाब तैयार नहीं हो सका, इसलिए अंग्रेज़ी में दिया है। "
              "{language} के लिए एक मिनट बाद फिर पूछिए।",
        "pa": "ਹੁਣੇ {language} ਵਿੱਚ ਜਵਾਬ ਤਿਆਰ ਨਹੀਂ ਹੋ ਸਕਿਆ, ਇਸ ਲਈ ਅੰਗਰੇਜ਼ੀ ਵਿੱਚ ਦਿੱਤਾ ਹੈ। "
              "{language} ਲਈ ਇੱਕ ਮਿੰਟ ਬਾਅਦ ਦੁਬਾਰਾ ਪੁੱਛੋ।",
        "mr": "आत्ता {language}मध्ये उत्तर तयार होऊ शकले नाही, म्हणून इंग्रजीत दिले आहे. "
              "{language}साठी एका मिनिटाने पुन्हा विचारा.",
    },

    # ── Web app (app/web) ────────────────────────────────────────────────────
    "web_greeting": {
        "en": "Namaste! How can I help your farm today?",
        "hi": "नमस्ते! आज आपके खेत के लिए क्या मदद करूँ?",
        "pa": "ਸਤ ਸ੍ਰੀ ਅਕਾਲ! ਅੱਜ ਤੁਹਾਡੇ ਖੇਤ ਲਈ ਕੀ ਮਦਦ ਕਰਾਂ?",
        "mr": "नमस्कार! आज तुमच्या शेतासाठी काय मदत करू?",
    },
    "web_choose_lang": {
        "en": "Choose your language", "hi": "अपनी भाषा चुनें",
        "pa": "ਆਪਣੀ ਭਾਸ਼ਾ ਚੁਣੋ", "mr": "तुमची भाषा निवडा",
    },
    "web_listening": {
        "en": "Listening… speak now", "hi": "सुन रहा हूँ… अब बोलिए",
        "pa": "ਸੁਣ ਰਿਹਾ ਹਾਂ… ਹੁਣ ਬੋਲੋ", "mr": "ऐकत आहे… आता बोला",
    },
    "web_thinking": {
        "en": "Thinking…", "hi": "सोच रहा हूँ…", "pa": "ਸੋਚ ਰਿਹਾ ਹਾਂ…", "mr": "विचार करत आहे…",
    },
    "web_cancel": {"en": "Cancel", "hi": "रद्द करें", "pa": "ਰੱਦ ਕਰੋ", "mr": "रद्द करा"},
    "web_ask_placeholder": {
        "en": "Type your question…", "hi": "अपना सवाल लिखिए…",
        "pa": "ਆਪਣਾ ਸਵਾਲ ਲਿਖੋ…", "mr": "तुमचा प्रश्न लिहा…",
    },
    "web_send": {"en": "Send", "hi": "भेजें", "pa": "ਭੇਜੋ", "mr": "पाठवा"},
    "web_listen": {"en": "Listen", "hi": "सुनें", "pa": "ਸੁਣੋ", "mr": "ऐका"},
    "web_pause": {"en": "Pause", "hi": "रोकें", "pa": "ਰੋਕੋ", "mr": "थांबवा"},
    "web_copy": {"en": "Copy", "hi": "कॉपी करें", "pa": "ਕਾਪੀ ਕਰੋ", "mr": "कॉपी करा"},
    "web_copied": {"en": "Copied", "hi": "कॉपी हो गया", "pa": "ਕਾਪੀ ਹੋ ਗਿਆ", "mr": "कॉपी झाले"},
    "web_share": {
        "en": "WhatsApp", "hi": "व्हाट्सऐप", "pa": "ਵਟਸਐਪ", "mr": "व्हॉट्सॲप",
    },
    "web_install": {
        "en": "Install app", "hi": "ऐप इंस्टॉल करें", "pa": "ਐਪ ਇੰਸਟਾਲ ਕਰੋ", "mr": "ॲप इंस्टॉल करा",
    },
    "web_theme": {
        "en": "Light or dark", "hi": "हल्की या गहरी थीम",
        "pa": "ਹਲਕੀ ਜਾਂ ਗੂੜ੍ਹੀ ਥੀਮ", "mr": "फिकट किंवा गडद थीम",
    },
    "web_save": {"en": "Save", "hi": "सेव करें", "pa": "ਸੇਵ ਕਰੋ", "mr": "जतन करा"},
    "web_add_village": {
        "en": "Add your village", "hi": "अपना गाँव जोड़ें",
        "pa": "ਆਪਣਾ ਪਿੰਡ ਜੋੜੋ", "mr": "तुमचे गाव जोडा",
    },
    "web_mic_denied": {
        "en": "Microphone permission is blocked. Allow it in your browser settings, "
              "or type your question.",
        "hi": "माइक की अनुमति बंद है। ब्राउज़र की सेटिंग में अनुमति दें, या सवाल लिखिए।",
        "pa": "ਮਾਈਕ ਦੀ ਇਜਾਜ਼ਤ ਬੰਦ ਹੈ। ਬ੍ਰਾਊਜ਼ਰ ਦੀ ਸੈਟਿੰਗ ਵਿੱਚ ਇਜਾਜ਼ਤ ਦਿਓ, ਜਾਂ ਸਵਾਲ ਲਿਖੋ।",
        "mr": "माइकची परवानगी बंद आहे. ब्राउझरच्या सेटिंगमध्ये परवानगी द्या, किंवा प्रश्न लिहा.",
    },
    "web_mic_missing": {
        "en": "No microphone was found on this device. Please type your question.",
        "hi": "इस डिवाइस में माइक नहीं मिला। कृपया सवाल लिखिए।",
        "pa": "ਇਸ ਡਿਵਾਈਸ 'ਤੇ ਮਾਈਕ ਨਹੀਂ ਮਿਲਿਆ। ਕਿਰਪਾ ਕਰਕੇ ਸਵਾਲ ਲਿਖੋ।",
        "mr": "या उपकरणावर माइक सापडला नाही. कृपया प्रश्न लिहा.",
    },
    "web_too_short": {
        "en": "That was too short — please speak your full question.",
        "hi": "यह बहुत छोटा था — कृपया पूरा सवाल बोलिए।",
        "pa": "ਇਹ ਬਹੁਤ ਛੋਟਾ ਸੀ — ਕਿਰਪਾ ਕਰਕੇ ਪੂਰਾ ਸਵਾਲ ਬੋਲੋ।",
        "mr": "हे खूप लहान होते — कृपया पूर्ण प्रश्न बोला.",
    },
    "web_offline": {
        "en": "You're offline. Answers need the internet.",
        "hi": "आप ऑफ़लाइन हैं। जवाब के लिए इंटरनेट चाहिए।",
        "pa": "ਤੁਸੀਂ ਆਫ਼ਲਾਈਨ ਹੋ। ਜਵਾਬ ਲਈ ਇੰਟਰਨੈੱਟ ਚਾਹੀਦਾ ਹੈ।",
        "mr": "तुम्ही ऑफलाइन आहात. उत्तरासाठी इंटरनेट हवे.",
    },
    "web_waking": {
        "en": "Waking up the assistant — the first answer can take up to a minute.",
        "hi": "सहायक तैयार हो रहा है — पहले जवाब में एक मिनट तक लग सकता है।",
        "pa": "ਸਹਾਇਕ ਤਿਆਰ ਹੋ ਰਿਹਾ ਹੈ — ਪਹਿਲੇ ਜਵਾਬ ਵਿੱਚ ਇੱਕ ਮਿੰਟ ਤੱਕ ਲੱਗ ਸਕਦਾ ਹੈ।",
        "mr": "सहाय्यक तयार होत आहे — पहिल्या उत्तराला एक मिनिट लागू शकतो.",
    },
    "web_error": {
        "en": "Something went wrong. Please try again.",
        "hi": "कुछ गड़बड़ हो गई। कृपया फिर से कोशिश करें।",
        "pa": "ਕੁਝ ਗੜਬੜ ਹੋ ਗਈ। ਕਿਰਪਾ ਕਰਕੇ ਦੁਬਾਰਾ ਕੋਸ਼ਿਸ਼ ਕਰੋ।",
        "mr": "काहीतरी चुकले. कृपया पुन्हा प्रयत्न करा.",
    },
    "web_gps_failed": {
        "en": "Could not get your location. Please type your village.",
        "hi": "आपकी लोकेशन नहीं मिल पाई। कृपया गाँव का नाम लिखिए।",
        "pa": "ਤੁਹਾਡੀ ਲੋਕੇਸ਼ਨ ਨਹੀਂ ਮਿਲੀ। ਕਿਰਪਾ ਕਰਕੇ ਪਿੰਡ ਦਾ ਨਾਮ ਲਿਖੋ।",
        "mr": "तुमचे ठिकाण मिळाले नाही. कृपया गावाचे नाव लिहा.",
    },
    "web_days": {"en": "days", "hi": "दिन", "pa": "ਦਿਨ", "mr": "दिवस"},
    "web_day_of": {  # {days} of {total}
        "en": "Day {days} of {total}", "hi": "{total} में से दिन {days}",
        "pa": "{total} ਵਿੱਚੋਂ ਦਿਨ {days}", "mr": "{total} पैकी दिवस {days}",
    },
    "web_now": {"en": "Now", "hi": "अभी", "pa": "ਹੁਣ", "mr": "आत्ता"},
    "web_humidity": {"en": "Humidity", "hi": "नमी", "pa": "ਨਮੀ", "mr": "आर्द्रता"},
    "web_wind": {"en": "Wind", "hi": "हवा", "pa": "ਹਵਾ", "mr": "वारा"},
    "web_rain": {"en": "Rain", "hi": "बारिश", "pa": "ਮੀਂਹ", "mr": "पाऊस"},
    "web_source": {"en": "Source", "hi": "स्रोत", "pa": "ਸਰੋਤ", "mr": "स्रोत"},
    "web_powered": {
        "en": "Answers come only from a crop guide, live weather and official scheme documents.",
        "hi": "जवाब सिर्फ़ फसल गाइड, ताज़ा मौसम और सरकारी योजना के दस्तावेज़ों से आते हैं।",
        "pa": "ਜਵਾਬ ਸਿਰਫ਼ ਫ਼ਸਲ ਗਾਈਡ, ਤਾਜ਼ਾ ਮੌਸਮ ਅਤੇ ਸਰਕਾਰੀ ਸਕੀਮ ਦੇ ਦਸਤਾਵੇਜ਼ਾਂ ਤੋਂ ਆਉਂਦੇ ਹਨ।",
        "mr": "उत्तरे फक्त पीक मार्गदर्शक, ताजे हवामान आणि सरकारी योजनांच्या कागदपत्रांतून येतात.",
    },
}

# Crop names as a farmer says them, per language (from the crop guides).
CROP_NAMES = knowledge.crop_names()

_AND = {"en": "and", "hi": "और", "pa": "ਅਤੇ", "mr": "आणि"}


def spoken_list(items: list[str], lang: str) -> str:
    """'a, b and c' in the given language."""
    if len(items) < 2:
        return "".join(items)
    return f"{', '.join(items[:-1])} {_AND[lang]} {items[-1]}"


# The lists inside the messages come from the knowledge base, so a new crop
# guide or scheme document shows up in them without touching this file.
for _lang in ("en", "hi", "pa", "mr"):
    _fill = {
        "{count}": str(len(CROP_NAMES)),
        "{crops}": spoken_list([names[_lang] for names in CROP_NAMES.values()], _lang),
        "{schemes}": spoken_list(knowledge.scheme_names(_lang), _lang),
    }
    for _key in ("help_crop", "ask_unsupported_crop", "ask_scheme_unknown"):
        for _token, _value in _fill.items():
            STRINGS[_key][_lang] = STRINGS[_key][_lang].replace(_token, _value)

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


def crop_label(crop: str, lang: str | None) -> str:
    """A knowledge-base crop's name in the chosen language."""
    names = CROP_NAMES.get(crop)
    return names[normalize_lang(lang)] if names else crop
