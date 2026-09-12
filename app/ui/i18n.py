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
    "hero_title": {  # HTML — <em> marks the accented phrase
        "en": "Ask in your<br><em>own language.</em>",
        "hi": "पूछिए<br><em>अपनी भाषा में।</em>",
        "pa": "ਪੁੱਛੋ<br><em>ਆਪਣੀ ਭਾਸ਼ਾ ਵਿੱਚ।</em>",
        "mr": "विचारा<br><em>तुमच्या भाषेत.</em>",
    },

    # ── Ask panel ────────────────────────────────────────────────────────────
    "lite_note": {  # shown only when this build has no speech engine
        "en": "This lightweight version takes typed questions and answers in English.",
        "hi": "इस हल्के संस्करण में सवाल लिखकर पूछिए; जवाब अंग्रेज़ी में मिलेगा।",
        "pa": "ਇਸ ਹਲਕੇ ਸੰਸਕਰਣ ਵਿੱਚ ਸਵਾਲ ਲਿਖ ਕੇ ਪੁੱਛੋ; ਜਵਾਬ ਅੰਗਰੇਜ਼ੀ ਵਿੱਚ ਮਿਲੇਗਾ।",
        "mr": "या हलक्या आवृत्तीत प्रश्न लिहून विचारा; उत्तर इंग्रजीत मिळेल.",
    },
    "hero_sub": {
        "en": "Crop care · Weather · Government schemes",
        "hi": "फसल की देखभाल · मौसम · सरकारी योजनाएँ",
        "pa": "ਫ਼ਸਲ ਦੀ ਸੰਭਾਲ · ਮੌਸਮ · ਸਰਕਾਰੀ ਸਕੀਮਾਂ",
        "mr": "पिकाची काळजी · हवामान · सरकारी योजना",
    },
    "mic_cta": {
        "en": "Tap the microphone, speak, then tap stop.",
        "hi": "माइक दबाइए, बोलिए, फिर रोकिए।",
        "pa": "ਮਾਈਕ ਦਬਾਓ, ਬੋਲੋ, ਫਿਰ ਰੋਕੋ।",
        "mr": "माइक दाबा, बोला, मग थांबवा.",
    },
    "examples_label": {
        "en": "Try asking", "hi": "ये पूछकर देखिए",
        "pa": "ਇਹ ਪੁੱਛ ਕੇ ਵੇਖੋ", "mr": "हे विचारून पाहा",
    },
    "replay_button": {
        "en": "🔊 Listen again", "hi": "🔊 फिर से सुनिए",
        "pa": "🔊 ਦੁਬਾਰਾ ਸੁਣੋ", "mr": "🔊 पुन्हा ऐका",
    },
    "typed_toggle": {
        "en": "Ask by typing", "hi": "लिखकर पूछिए",
        "pa": "ਲਿਖ ਕੇ ਪੁੱਛੋ", "mr": "लिहून विचारा",
    },
    "place_label": {
        "en": "📍 My village", "hi": "📍 मेरा गाँव",
        "pa": "📍 ਮੇਰਾ ਪਿੰਡ", "mr": "📍 माझे गाव",
    },
    "ask_button": {
        "en": "Ask the assistant", "hi": "सहायक से पूछिए",
        "pa": "ਸਹਾਇਕ ਨੂੰ ਪੁੱਛੋ", "mr": "सहाय्यकाला विचारा",
    },
    "pending": {
        "en": "Awaiting your question", "hi": "आपके सवाल का इंतज़ार",
        "pa": "ਤੁਹਾਡੇ ਸਵਾਲ ਦੀ ਉਡੀਕ", "mr": "तुमच्या प्रश्नाची प्रतीक्षा",
    },
    "mode_typed": {"en": "typed", "hi": "लिखकर", "pa": "ਲਿਖ ਕੇ", "mr": "लिहून"},
    "mode_voice": {"en": "voice", "hi": "आवाज़ से", "pa": "ਆਵਾਜ਼ ਨਾਲ", "mr": "आवाजाने"},

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
    "tool_crop": {"en": "Crop knowledge", "hi": "फसल जानकारी", "pa": "ਫ਼ਸਲ ਜਾਣਕਾਰੀ", "mr": "पीक माहिती"},
    "tool_weather": {"en": "Weather", "hi": "मौसम", "pa": "ਮੌਸਮ", "mr": "हवामान"},
    "tool_scheme": {"en": "Govt scheme", "hi": "सरकारी योजना", "pa": "ਸਰਕਾਰੀ ਯੋਜਨਾ", "mr": "सरकारी योजना"},
    "chip_used": {"en": "used", "hi": "उपयोग हुआ", "pa": "ਵਰਤਿਆ", "mr": "वापरले"},

    # ── Diagnostics & footer ─────────────────────────────────────────────────
    "diag": {
        "en": "Transcript & pipeline", "hi": "प्रतिलेख और प्रक्रिया",
        "pa": "ਲਿਖਤ ਅਤੇ ਪ੍ਰਕਿਰਿਆ", "mr": "प्रतिलेख आणि प्रक्रिया",
    },
    "heard_label": {"en": "Heard", "hi": "सुना गया", "pa": "ਸੁਣਿਆ ਗਿਆ", "mr": "ऐकलेले"},
    "english_label": {
        "en": "English translation", "hi": "अंग्रेज़ी अनुवाद",
        "pa": "ਅੰਗਰੇਜ਼ੀ ਅਨੁਵਾਦ", "mr": "इंग्रजी भाषांतर",
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

    # ══ Voice + regional build (Groq, or IndicTrans2) ════════════════════════
    # Used instead of the "in English" wording above when the app can hear and
    # answer every language.
    "text_placeholder_native": {
        "en": "Will it rain in Pune tomorrow? Any scheme for irrigation?",
        "hi": "यहाँ लिखिए, जैसे: क्या कल पुणे में बारिश होगी?",
        "pa": "ਇੱਥੇ ਲਿਖੋ, ਜਿਵੇਂ: ਕੀ ਕੱਲ੍ਹ ਲੁਧਿਆਣਾ ਵਿੱਚ ਮੀਂਹ ਪਵੇਗਾ?",
        "mr": "येथे लिहा, उदा.: उद्या नाशिकमध्ये पाऊस येईल का?",
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
    "help_crop": {
        "en": "🌾 Crop care — fertilizer, water, pests and disease — for wheat, rice, "
              "cotton, onion, tomato and maize",
        "hi": "🌾 फसल की देखभाल — खाद, पानी, कीड़े और रोग — गेहूं, धान, कपास, प्याज, "
              "टमाटर और मक्का के लिए",
        "pa": "🌾 ਫ਼ਸਲ ਦੀ ਸੰਭਾਲ — ਖਾਦ, ਪਾਣੀ, ਕੀੜੇ ਅਤੇ ਰੋਗ — ਕਣਕ, ਝੋਨਾ, ਕਪਾਹ, ਪਿਆਜ਼, "
              "ਟਮਾਟਰ ਅਤੇ ਮੱਕੀ ਲਈ",
        "mr": "🌾 पिकाची काळजी — खत, पाणी, कीड आणि रोग — गहू, भात, कापूस, कांदा, "
              "टोमॅटो आणि मका यांसाठी",
    },
    "help_weather": {
        "en": "🌦 Weather — rain, heat and wind for your village, for the next 3 days",
        "hi": "🌦 मौसम — आपके गाँव में बारिश, गर्मी और हवा, अगले 3 दिन",
        "pa": "🌦 ਮੌਸਮ — ਤੁਹਾਡੇ ਪਿੰਡ ਵਿੱਚ ਮੀਂਹ, ਗਰਮੀ ਅਤੇ ਹਵਾ, ਅਗਲੇ 3 ਦਿਨ",
        "mr": "🌦 हवामान — तुमच्या गावातील पाऊस, उष्णता आणि वारा, पुढील 3 दिवस",
    },
    "help_scheme": {
        "en": "🏛 Government schemes — PM-KISAN, crop insurance (PMFBY), Kisan Credit "
              "Card, Soil Health Card",
        "hi": "🏛 सरकारी योजनाएँ — पीएम किसान, फसल बीमा (PMFBY), किसान क्रेडिट कार्ड, "
              "मृदा स्वास्थ्य कार्ड",
        "pa": "🏛 ਸਰਕਾਰੀ ਸਕੀਮਾਂ — ਪੀਐਮ ਕਿਸਾਨ, ਫ਼ਸਲ ਬੀਮਾ (PMFBY), ਕਿਸਾਨ ਕ੍ਰੈਡਿਟ ਕਾਰਡ, "
              "ਸੋਇਲ ਹੈਲਥ ਕਾਰਡ",
        "mr": "🏛 सरकारी योजना — पीएम किसान, पीक विमा (PMFBY), किसान क्रेडिट कार्ड, "
              "मृदा आरोग्य पत्रिका",
    },
    "heard_prefix": {"en": "You asked", "hi": "आपने पूछा", "pa": "ਤੁਸੀਂ ਪੁੱਛਿਆ", "mr": "तुम्ही विचारले"},

    # ── Questions back to the farmer (shown and spoken) ──────────────────────
    "ask_crop": {
        "en": "Which crop is this about? I can advise on wheat, rice, cotton, onion, "
              "tomato and maize.",
        "hi": "यह किस फसल के बारे में है? मैं गेहूं, धान, कपास, प्याज, टमाटर और मक्का के "
              "बारे में सलाह दे सकता हूँ।",
        "pa": "ਇਹ ਕਿਹੜੀ ਫ਼ਸਲ ਬਾਰੇ ਹੈ? ਮੈਂ ਕਣਕ, ਝੋਨਾ, ਕਪਾਹ, ਪਿਆਜ਼, ਟਮਾਟਰ ਅਤੇ ਮੱਕੀ ਬਾਰੇ "
              "ਸਲਾਹ ਦੇ ਸਕਦਾ ਹਾਂ।",
        "mr": "हे कोणत्या पिकाबद्दल आहे? मी गहू, भात, कापूस, कांदा, टोमॅटो आणि मका "
              "यांबद्दल सल्ला देऊ शकतो.",
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
        "en": "I don't have advice for {crop} yet. I can help with wheat, rice, cotton, "
              "onion, tomato and maize.",
        "hi": "अभी मेरे पास {crop} के बारे में जानकारी नहीं है। मैं गेहूं, धान, कपास, "
              "प्याज, टमाटर और मक्का में मदद कर सकता हूँ।",
        "pa": "ਅਜੇ ਮੇਰੇ ਕੋਲ {crop} ਬਾਰੇ ਜਾਣਕਾਰੀ ਨਹੀਂ ਹੈ। ਮੈਂ ਕਣਕ, ਝੋਨਾ, ਕਪਾਹ, ਪਿਆਜ਼, "
              "ਟਮਾਟਰ ਅਤੇ ਮੱਕੀ ਵਿੱਚ ਮਦਦ ਕਰ ਸਕਦਾ ਹਾਂ।",
        "mr": "सध्या माझ्याकडे {crop} बद्दल माहिती नाही. मी गहू, भात, कापूस, कांदा, "
              "टोमॅटो आणि मका यांबाबत मदत करू शकतो.",
    },
    "ask_scheme_unknown": {
        "en": "I don't have details of that scheme. I can tell you about PM-KISAN, crop "
              "insurance (PM Fasal Bima Yojana), Kisan Credit Card and Soil Health Card.",
        "hi": "उस योजना की जानकारी मेरे पास नहीं है। मैं पीएम किसान, फसल बीमा (प्रधानमंत्री "
              "फसल बीमा योजना), किसान क्रेडिट कार्ड और मृदा स्वास्थ्य कार्ड के बारे में "
              "बता सकता हूँ।",
        "pa": "ਉਸ ਸਕੀਮ ਦੀ ਜਾਣਕਾਰੀ ਮੇਰੇ ਕੋਲ ਨਹੀਂ ਹੈ। ਮੈਂ ਪੀਐਮ ਕਿਸਾਨ, ਫ਼ਸਲ ਬੀਮਾ (ਪ੍ਰਧਾਨ "
              "ਮੰਤਰੀ ਫ਼ਸਲ ਬੀਮਾ ਯੋਜਨਾ), ਕਿਸਾਨ ਕ੍ਰੈਡਿਟ ਕਾਰਡ ਅਤੇ ਸੋਇਲ ਹੈਲਥ ਕਾਰਡ ਬਾਰੇ "
              "ਦੱਸ ਸਕਦਾ ਹਾਂ।",
        "mr": "त्या योजनेची माहिती माझ्याकडे नाही. मी पीएम किसान, पीक विमा (प्रधानमंत्री "
              "पीक विमा योजना), किसान क्रेडिट कार्ड आणि मृदा आरोग्य पत्रिका यांबद्दल "
              "सांगू शकतो.",
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
}

# Crop names as a farmer says them, per language.
CROP_NAMES = {
    "wheat": {"en": "wheat", "hi": "गेहूं", "pa": "ਕਣਕ", "mr": "गहू"},
    "rice": {"en": "rice", "hi": "धान", "pa": "ਝੋਨਾ", "mr": "भात"},
    "onion": {"en": "onion", "hi": "प्याज", "pa": "ਪਿਆਜ਼", "mr": "कांदा"},
    "tomato": {"en": "tomato", "hi": "टमाटर", "pa": "ਟਮਾਟਰ", "mr": "टोमॅटो"},
    "cotton": {"en": "cotton", "hi": "कपास", "pa": "ਕਪਾਹ", "mr": "कापूस"},
    "maize": {"en": "maize", "hi": "मक्का", "pa": "ਮੱਕੀ", "mr": "मका"},
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


def crop_label(crop: str, lang: str | None) -> str:
    """A knowledge-base crop's name in the chosen language."""
    names = CROP_NAMES.get(crop)
    return names[normalize_lang(lang)] if names else crop
