// Agri Assistant — the web app.
// One small script, no framework (it has to open fast on a cheap phone on 3G).
// It talks to the JSON API in app/web/server.py.
"use strict";

const $ = (selector) => document.querySelector(selector);

const store = {
  get(key, fallback = null) {
    try { const v = localStorage.getItem(key); return v === null ? fallback : v; } catch (e) { return fallback; }
  },
  set(key, value) {
    try { value == null ? localStorage.removeItem(key) : localStorage.setItem(key, value); } catch (e) { /* private mode */ }
  },
};

const LOCALES = { en: "en-IN", hi: "hi-IN", pa: "pa-IN", mr: "mr-IN" };
const NATIVE = { en: "English", hi: "हिंदी", pa: "ਪੰਜਾਬੀ", mr: "मराठी" };
const EXAMPLE_ICONS = ["🌾", "🌦️", "🏛️", "🌿"];
const AGE_CHOICES = [20, 40, 60, 90];
const MAX_RECORDING_S = 60;
// A 44-byte silent WAV: played once on the first tap so the browser lets the
// spoken answers start on their own afterwards (iOS and Chrome autoplay rules).
const SILENCE = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=";

const state = {
  config: null,
  lang: "en",
  place: store.get("ag_place", ""),
  pending: null,        // the question waiting on a detail ("how many days old?")
  lastQuestion: "",     // the last full question, to ask again once a place is known
  busy: false,
  rec: null,            // the recording in progress
  speakAbort: null,     // the voice being fetched
  playing: null,        // the Listen button whose answer is playing
  installPrompt: null,
  audioUnlocked: false,
};

const el = {
  thread: $("#thread"), welcome: $("#welcome"), input: $("#input"), send: $("#sendBtn"),
  mic: $("#micBtn"), orb: $("#orbBtn"), quick: $("#quick"), dock: $("#dock"),
  player: $("#player"), toast: $("#toast"), recorder: $("#recorder"), wave: $("#wave"),
  recTime: $("#recTime"), langs: $("#langs"), langBtn: $("#langBtn"), langLabel: $("#langLabel"),
  langDialog: $("#langDialog"), langGrid: $("#langGrid"), langTitle: $("#langTitle"),
  placeBtn: $("#placeBtn"), placeLabel: $("#placeLabel"), placeDialog: $("#placeDialog"),
  placeInput: $("#placeInput"), newBtn: $("#newBtn"), themeBtn: $("#themeBtn"), installBtn: $("#installBtn"),
};

// ── Text in the chosen language ─────────────────────────────────────────────
function t(key, vars) {
  const strings = state.config ? state.config.strings : null;
  let text = strings ? (strings[state.lang] || {})[key] ?? strings.en[key] : null;
  if (text == null) text = key;
  return vars ? text.replace(/\{(\w+)\}/g, (_, name) => (vars[name] ?? "")) : text;
}

function escapeHtml(text) {
  return String(text ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function icon(name) {
  return `<svg class="ic" aria-hidden="true"><use href="#i-${name}"/></svg>`;
}

let toastTimer = null;
function toast(message, ms = 3600) {
  el.toast.textContent = message;
  el.toast.classList.add("is-on");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.toast.classList.remove("is-on"), ms);
}

// ── Language ─────────────────────────────────────────────────────────────────
function guessLanguage() {
  const nav = (navigator.language || "").toLowerCase();
  return ["hi", "pa", "mr"].find((code) => nav.startsWith(code)) || "en";
}

function heroBodyKey() {
  const { voice, regional } = state.config;
  if (voice && regional) return "hero_body_voice";
  return voice ? "hero_body_full" : "hero_body_lite";
}

function applyLanguage(lang) {
  state.lang = LOCALES[lang] ? lang : "en";
  store.set("ag_lang", state.lang);
  document.documentElement.lang = state.lang;

  document.querySelectorAll("[data-i18n]").forEach((node) => { node.textContent = t(node.dataset.i18n); });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => { node.placeholder = t(node.dataset.i18nPlaceholder); });
  document.querySelectorAll("[data-i18n-aria]").forEach((node) => {
    node.setAttribute("aria-label", t(node.dataset.i18nAria));
    node.title = t(node.dataset.i18nAria);
  });
  $(".lede").textContent = t(heroBodyKey());
  // Typed-only build (no speech service): questions are typed in English.
  if (!state.config.voice) el.input.placeholder = t("text_placeholder");

  el.langs.querySelectorAll("button").forEach((b) => b.setAttribute("aria-checked", String(b.dataset.lang === state.lang)));
  el.langLabel.textContent = NATIVE[state.lang];
  renderBento();
  renderExamples();
  renderPlace();
  if (state.pending) renderQuick(state.pending.missing || []);
}

function renderLanguageSwitch() {
  el.langs.innerHTML = state.config.languages.map(({ code }) =>
    `<button type="button" role="radio" data-lang="${code}" aria-checked="false" lang="${code}">${NATIVE[code]}</button>`).join("");
  el.langs.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-lang]");
    if (button) applyLanguage(button.dataset.lang);
  });
  el.langGrid.innerHTML = state.config.languages.map(({ code }) =>
    `<button type="button" data-lang="${code}" lang="${code}"><b>${NATIVE[code]}</b>` +
    `<span>${escapeHtml(state.config.lang_names.en[code])}</span></button>`).join("");
  el.langGrid.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-lang]");
    if (!button) return;
    applyLanguage(button.dataset.lang);
    el.langDialog.close();
  });
}

function openLanguageSheet(firstVisit) {
  const strings = state.config.strings;
  // On the first visit nobody knows the language yet: say it in all four.
  el.langTitle.innerHTML = firstVisit
    ? `${escapeHtml(strings[state.lang].web_choose_lang)}<small>${["en", "hi", "pa", "mr"]
        .filter((c) => c !== state.lang).map((c) => escapeHtml(strings[c].web_choose_lang)).join(" · ")}</small>`
    : escapeHtml(t("web_choose_lang"));
  el.langDialog.showModal();
}

// ── Welcome: what it can help with, sample questions ─────────────────────────
function renderBento() {
  const tiles = [["help_crop", "sprout"], ["help_weather", "cloud"], ["help_scheme", "landmark"]];
  $("#bento").innerHTML = tiles.map(([key, ic]) => {
    const [head, ...rest] = t(key).split(" — ");
    const title = head.replace(/^\S+\s/, "");          // drop the emoji; the tile has an icon
    const body = rest.join(" — ");
    return `<article class="tile"><span class="tile-icon">${icon(ic)}</span>` +
           `<h3>${escapeHtml(title)}</h3><p>${escapeHtml(body.charAt(0).toUpperCase() + body.slice(1))}</p></article>`;
  }).join("");
}

function renderExamples() {
  const examples = state.config.examples[state.lang] || [];
  const box = $("#examples");
  box.innerHTML = examples.map((text, i) =>
    `<button class="chip" type="button" data-q="${escapeHtml(text)}"><span class="emoji">${EXAMPLE_ICONS[i] || "🌱"}</span>${escapeHtml(text)}</button>`).join("");
}

// ── Village ──────────────────────────────────────────────────────────────────
const COORDS = /^\s*-?\d{1,2}(\.\d+)?\s*,\s*-?\d{1,3}(\.\d+)?\s*$/;

function placeName() {
  if (!state.place) return "";
  if (COORDS.test(state.place)) {
    const here = t("your_location");
    return here.charAt(0).toUpperCase() + here.slice(1);
  }
  return state.place;
}

function renderPlace() {
  el.placeLabel.textContent = placeName() || t("web_add_village");
  el.placeBtn.title = el.placeLabel.textContent;
  el.placeBtn.setAttribute("aria-label", t("eyebrow_location") + ": " + el.placeLabel.textContent);
}

function setPlace(value) {
  state.place = (value || "").trim().slice(0, 120);
  store.set("ag_place", state.place || null);
  renderPlace();
}

function locate() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) { reject(new Error("unsupported")); return; }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve(`${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)}`),
      reject, { enableHighAccuracy: false, timeout: 15000, maximumAge: 600000 });
  });
}

function openPlaceSheet(then) {
  el.placeInput.value = state.place;
  el.placeDialog._then = then || null;
  el.placeDialog.showModal();
  setTimeout(() => el.placeInput.focus(), 50);
}

// ── Conversation ─────────────────────────────────────────────────────────────
function scrollToEnd() {
  requestAnimationFrame(() => window.scrollTo({ top: document.documentElement.scrollHeight, behavior: "smooth" }));
}

function startConversation() {
  el.welcome.hidden = true;
  el.newBtn.hidden = false;
}

function addUser(text, mode) {
  startConversation();
  const row = document.createElement("div");
  row.className = "msg msg--user";
  row.innerHTML = `<div class="bubble-user">${mode === "voice" ? '<span class="via">🎙</span>' : ""}<span class="words"></span></div>`;
  row.querySelector(".words").textContent = text;
  el.thread.appendChild(row);
  scrollToEnd();
  return row;
}

function addPending() {
  const row = document.createElement("div");
  row.className = "msg msg--bot";
  row.innerHTML = `<span class="avatar"><svg><use href="#i-wheat"/></svg></span>` +
    `<div class="reply"><div class="bubble-bot"><span class="typing"><span class="dots"><i></i><i></i><i></i></span>` +
    `<span>${escapeHtml(t("web_thinking"))}</span></span></div></div>`;
  el.thread.appendChild(row);
  scrollToEnd();
  // Free hosting sleeps when idle; say so if the first answer is slow.
  row._slow = setTimeout(() => {
    const note = document.createElement("span");
    note.className = "waking";
    note.textContent = t("web_waking");
    row.querySelector(".bubble-bot").appendChild(note);
  }, 9000);
  return row;
}

function formatAnswer(text) {
  const inline = (s) => escapeHtml(s).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  const blocks = [];
  let list = null;
  for (const raw of String(text || "").split("\n")) {
    const line = raw.trim();
    const numbered = line.match(/^(\d+)[.)]\s+(.*)$/);
    const bullet = line.match(/^[-•*]\s+(.*)$/);
    if (numbered || bullet) {
      const kind = numbered ? "ol" : "ul";
      if (!list || list.kind !== kind) { list = { kind, items: [] }; blocks.push(list); }
      list.items.push(inline(numbered ? numbered[2] : bullet[1]));
      continue;
    }
    list = null;
    if (line) blocks.push(`<p>${inline(line)}</p>`);
  }
  return blocks.map((b) => (typeof b === "string" ? b
    : `<${b.kind}>${b.items.map((item) => `<li>${item}</li>`).join("")}</${b.kind}>`)).join("");
}

const WEATHER_EMOJI = [[[0], "☀️"], [[1], "🌤️"], [[2], "⛅"], [[3], "☁️"], [[45, 48], "🌫️"],
  [[51, 53, 55, 56, 57], "🌦️"], [[61, 63, 65, 66, 67, 80, 81, 82], "🌧️"],
  [[71, 73, 75, 77, 85, 86], "🌨️"], [[95, 96, 99], "⛈️"]];
function weatherEmoji(code) {
  const hit = WEATHER_EMOJI.find(([codes]) => codes.includes(code));
  return hit ? hit[1] : "🌡️";
}
const round = (n) => (n == null || Number.isNaN(Number(n)) ? "–" : Math.round(Number(n)));

function weatherCard(w) {
  const place = w.gps ? placeName() || t("your_location") : w.place;
  const weekday = new Intl.DateTimeFormat(LOCALES[state.lang], { weekday: "short" });
  const days = (w.days || []).slice(1, 4).map((d) => {
    const date = new Date(`${d.date}T12:00:00`);
    const rain = Number(d.rain_mm) > 0 ? `${Number(d.rain_mm).toFixed(1)} mm`
      : d.rain_pct != null ? `${d.rain_pct}%` : "0 mm";
    return `<div class="wx-day"><b>${escapeHtml(weekday.format(date))}</b><span class="e">${weatherEmoji(d.code)}</span>` +
           `<span class="t">${round(d.max)}° / ${round(d.min)}°</span><span class="r">💧 ${escapeHtml(rain)}</span></div>`;
  }).join("");
  const now = w.now || {};
  return `<section class="card card--weather"><div class="card-head"><span>${icon("cloud")}${escapeHtml(place)}</span>` +
    `<span>${escapeHtml(w.source || "")}</span></div>` +
    `<div class="wx-now"><span class="wx-emoji">${weatherEmoji(now.code)}</span><span class="wx-temp">${round(now.temp)}°</span>` +
    `<span class="wx-meta"><span>${escapeHtml(t("web_humidity"))} ${round(now.humidity)}%</span>` +
    `<span>${escapeHtml(t("web_wind"))} ${round(now.wind)} km/h</span></span></div>` +
    `<div class="wx-days">${days}</div></section>`;
}

function cropCard(c) {
  const raw = (state.config.crops[c.crop] || {})[state.lang] || c.crop;
  const name = raw.charAt(0).toUpperCase() + raw.slice(1);
  const total = c.total_days || c.to || c.days;
  const pct = Math.max(4, Math.min(100, Math.round((c.days / total) * 100)));
  return `<section class="card card--crop"><div class="card-head"><span>${icon("sprout")}${escapeHtml(name)}</span>` +
    `<span>${escapeHtml(t("web_day_of", { days: c.days, total }))}</span></div>` +
    `<p class="stage-name">${escapeHtml(c.stage)}</p>` +
    `<div class="progress"><i style="width:${pct}%"></i></div>` +
    `<div class="progress-label"><span>0</span><span>${escapeHtml(String(total))} ${escapeHtml(t("web_days"))}</span></div></section>`;
}

function schemeCard(names) {
  return `<section class="card card--scheme"><div class="card-head"><span>${icon("landmark")}${escapeHtml(t("web_source"))}</span></div>` +
    `<div class="doc-chips">${names.map((n) => `<span class="doc-chip">📄 ${escapeHtml(n)}</span>`).join("")}</div></section>`;
}

function showAnswer(row, data, question) {
  clearTimeout(row._slow);
  const tools = data.tools || {};
  const sources = [["crop", "sprout", "tool_crop"], ["weather", "cloud", "tool_weather"], ["scheme", "landmark", "tool_scheme"]]
    .filter(([key]) => tools[key])
    .map(([, ic, label]) => `<span class="src">${icon(ic)}${escapeHtml(t(label))}</span>`).join("");
  const cards = data.cards || {};
  const cardHtml = [cards.weather ? weatherCard(cards.weather) : "", cards.crop ? cropCard(cards.crop) : "",
                    cards.schemes && cards.schemes.length ? schemeCard(cards.schemes) : ""].join("");

  const reply = row.querySelector(".reply");
  reply.innerHTML =
    `<div class="bubble-bot">${formatAnswer(data.answer)}</div>` +
    (sources ? `<div class="sources">${sources}</div>` : "") +
    (cardHtml ? `<div class="cards">${cardHtml}</div>` : "") +
    `<div class="actions">` +
      `<button class="act act--listen" type="button" data-act="listen">${icon("play")}<span>${escapeHtml(t("web_listen"))}</span><i class="bar"></i></button>` +
      `<button class="act" type="button" data-act="copy">${icon("copy")}<span>${escapeHtml(t("web_copy"))}</span></button>` +
      `<button class="act" type="button" data-act="share">${icon("share")}<span>${escapeHtml(t("web_share"))}</span></button>` +
      `<button class="act act--icon" type="button" data-act="details" aria-expanded="false" aria-label="${escapeHtml(t("diag"))}" title="${escapeHtml(t("diag"))}">${icon("info")}</button>` +
    `</div>`;

  const listen = reply.querySelector('[data-act="listen"]');
  listen._speech = data.speech;
  row._data = { answer: data.answer, question };

  reply.querySelector('[data-act="details"]').addEventListener("click", (event) => toggleDetails(reply, data, event.currentTarget));
  reply.querySelector('[data-act="copy"]').addEventListener("click", () => copyText(data.answer));
  reply.querySelector('[data-act="share"]').addEventListener("click", () => shareWhatsApp(question, data.answer));
  listen.addEventListener("click", () => toggleSpeech(listen));

  state.pending = data.pending || null;
  renderQuick(data.missing || []);
  scrollToEnd();
  // Speak the answer straight away — the farmer may not read.
  if (data.speech && data.speech.text) toggleSpeech(listen, true);
}

function showError(row, message, retry) {
  clearTimeout(row._slow);
  const reply = row.querySelector(".reply");
  reply.innerHTML = `<div class="bubble-bot is-error"><p>${escapeHtml(message)}</p></div>` +
    `<div class="actions"><button class="act" type="button">${icon("retry")}<span>${escapeHtml(t("web_send"))}</span></button></div>`;
  reply.querySelector("button").addEventListener("click", () => { row.remove(); retry(); });
  scrollToEnd();
}

function toggleDetails(reply, data, button) {
  const open = reply.querySelector(".details");
  if (open) { open.remove(); button.setAttribute("aria-expanded", "false"); return; }
  const names = state.config.lang_names[state.lang] || state.config.lang_names.en;
  const rows = [
    [t("heard_label"), data.heard],
    [t("eyebrow_detected"), `${names[data.question_lang] || data.question_lang} · ${t("mode_" + data.mode)}`],
    [t("english_label"), data.english],
    ["⏱", `${(data.ms / 1000).toFixed(1)} s`],
  ].filter(([, v]) => v);
  const box = document.createElement("div");
  box.className = "details";
  box.innerHTML = `<dl>${rows.map(([k, v]) => `<dt>${escapeHtml(k)}</dt><dd>${escapeHtml(v)}</dd>`).join("")}</dl>` +
    (data.understood ? `<pre>${escapeHtml(data.understood)}</pre>` : "") +
    (data.trace ? `<pre>${escapeHtml(data.trace)}</pre>` : "");
  reply.appendChild(box);
  button.setAttribute("aria-expanded", "true");
}

// ── Quick replies to a question the assistant asked back ─────────────────────
function renderQuick(missing) {
  const chips = [];
  if (missing.includes("age")) {
    AGE_CHOICES.forEach((n) => chips.push({ label: `${n} ${t("web_days")}`, send: `${n} ${t("web_days")}` }));
  }
  if (missing.includes("crop")) {
    Object.values(state.config.crops).forEach((names) => chips.push({ label: names[state.lang], send: names[state.lang] }));
  }
  if (missing.includes("location")) {
    chips.push({ label: `📍 ${t("gps_button").replace(/^📍\s*/, "")}`, action: "gps" });
    chips.push({ label: `✏️ ${t("web_add_village")}`, action: "village" });
  }
  el.quick.innerHTML = chips.map((c, i) => `<button class="chip" type="button" data-i="${i}">${escapeHtml(c.label)}</button>`).join("");
  el.quick._chips = chips;
  syncDock();
}

async function onQuick(chip) {
  if (chip.send) { ask(chip.send); return; }
  if (chip.action === "gps") {
    try { setPlace(await locate()); } catch (e) { toast(t("web_gps_failed")); return; }
    askAgainWithPlace();
  } else if (chip.action === "village") {
    openPlaceSheet(askAgainWithPlace);
  }
}

function askAgainWithPlace() {
  // The place answers the question that was asked back: ask that question again.
  if (state.lastQuestion) ask(state.lastQuestion, { fresh: true });
}

// ── Asking ───────────────────────────────────────────────────────────────────
function setBusy(busy) {
  state.busy = busy;
  el.mic.disabled = busy;
  el.orb.disabled = busy;
  updateSend();
}

function updateSend() {
  el.send.disabled = state.busy || !el.input.value.trim();
}

async function api(path, body, { form = false, timeout = 120000 } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(path, {
      method: "POST",
      body: form ? body : JSON.stringify(body),
      headers: form ? {} : { "Content-Type": "application/json" },
      signal: controller.signal,
    });
    let data = null;
    try { data = await response.json(); } catch (e) { /* not JSON */ }
    if (!response.ok) {
      const detail = data && (data.error || (typeof data.detail === "string" ? data.detail : null));
      throw new Error(detail || t("web_error"));
    }
    return data;
  } catch (err) {
    if (!navigator.onLine) throw new Error(t("web_offline"));
    if (err.name === "AbortError" || err instanceof TypeError) throw new Error(t("web_error"));
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

async function ask(text, { fresh = false } = {}) {
  text = (text || "").trim();
  if (!text || state.busy) return;
  stopSpeech();
  el.quick.innerHTML = "";
  const pending = fresh ? null : state.pending;
  if (!pending) state.lastQuestion = text;
  addUser(text, "typed");
  const row = addPending();
  setBusy(true);
  try {
    const data = await api("/api/ask", { text, lang: state.lang, location: state.place, pending });
    showAnswer(row, data, text);
  } catch (err) {
    showError(row, err.message, () => ask(text, { fresh }));
  } finally {
    setBusy(false);
  }
}

async function askByVoice(blob) {
  stopSpeech();
  el.quick.innerHTML = "";
  const userRow = addUser(t("voice_question"), "voice");
  const row = addPending();
  setBusy(true);
  const form = new FormData();
  const ext = blob.type.includes("mp4") ? "m4a" : blob.type.includes("ogg") ? "ogg" : "webm";
  form.append("audio", blob, `question.${ext}`);
  form.append("lang", state.lang);
  form.append("location", state.place);
  form.append("pending", state.pending ? JSON.stringify(state.pending) : "");
  try {
    const data = await api("/api/voice", form, { form: true });
    if (data.heard) {
      userRow.querySelector(".words").textContent = data.heard;
      // A reply to an ask-back ("40 days") isn't a question to ask again.
      if (!state.pending) state.lastQuestion = data.heard;
    }
    showAnswer(row, data, data.heard || "");
  } catch (err) {
    showError(row, err.message, () => { userRow.remove(); askByVoice(blob); });
  } finally {
    setBusy(false);
  }
}

function newConversation() {
  stopSpeech();
  el.thread.querySelectorAll(".act--listen").forEach((b) => b._url && URL.revokeObjectURL(b._url));
  el.thread.innerHTML = "";
  el.quick.innerHTML = "";
  state.pending = null;
  state.lastQuestion = "";
  el.welcome.hidden = false;
  el.newBtn.hidden = true;
  syncDock();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

// ── The spoken answer ────────────────────────────────────────────────────────
function unlockAudio() {
  if (state.audioUnlocked) return;
  state.audioUnlocked = true;
  try { el.player.src = SILENCE; el.player.play().catch(() => {}); } catch (e) { /* ignore */ }
}

function setListenButton(button, playing) {
  if (!button) return;
  button.querySelector("use").setAttribute("href", playing ? "#i-pause" : "#i-play");
  button.querySelector("span").textContent = t(playing ? "web_pause" : "web_listen");
}

function stopSpeech() {
  if (state.speakAbort) { state.speakAbort.abort(); state.speakAbort = null; }
  el.player.pause();
  if (state.playing) state.playing.querySelector(".bar").style.width = "0";
  setListenButton(state.playing, false);
  state.playing = null;
}

async function toggleSpeech(button, auto = false) {
  if (state.playing === button && !el.player.paused) {   // pause
    el.player.pause();
    setListenButton(button, false);
    return;
  }
  if (state.playing === button && el.player.src === button._url && el.player.currentTime > 0
      && !el.player.ended) {                                // resume
    el.player.play().then(() => setListenButton(button, true)).catch(() => {});
    return;
  }
  stopSpeech();
  if (!button._url) {
    const speech = button._speech;
    if (!speech || !speech.text) return;
    button.classList.add("is-loading");
    const controller = new AbortController();
    state.speakAbort = controller;
    try {
      const response = await fetch("/api/speak", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: speech.text, lang: speech.lang }), signal: controller.signal,
      });
      if (!response.ok) throw new Error(String(response.status));
      button._url = URL.createObjectURL(await response.blob());
    } catch (err) {
      if (err.name !== "AbortError" && !auto) toast(t("err_service"));
      return;
    } finally {
      button.classList.remove("is-loading");
      if (state.speakAbort === controller) state.speakAbort = null;
    }
  }
  state.playing = button;
  el.player.src = button._url;
  try {
    await el.player.play();
    setListenButton(button, true);
  } catch (e) {
    // The browser blocked autoplay — the Listen button still works.
    setListenButton(button, false);
  }
}

el.player.addEventListener("timeupdate", () => {
  const button = state.playing;
  if (!button || !el.player.duration) return;
  button.querySelector(".bar").style.width = `${(el.player.currentTime / el.player.duration) * 100}%`;
});
el.player.addEventListener("ended", () => {
  if (state.playing) state.playing.querySelector(".bar").style.width = "0";
  setListenButton(state.playing, false);
  state.playing = null;
});

// ── Copy and share ───────────────────────────────────────────────────────────
async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
  } catch (e) {
    const area = document.createElement("textarea");
    area.value = text;
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    document.execCommand("copy");
    area.remove();
  }
  toast(`✓ ${t("web_copied")}`, 1800);
}

function shareWhatsApp(question, answer) {
  const message = `${question ? `❓ ${question}\n\n` : ""}${answer}\n\n— ${t("brand")} · ${location.origin}`;
  // api.whatsapp.com rather than wa.me: wa.me's redirect garbles emoji.
  window.open(`https://api.whatsapp.com/send?text=${encodeURIComponent(message)}`, "_blank", "noopener");
}

// ── Recording ────────────────────────────────────────────────────────────────
function pickMimeType() {
  if (!window.MediaRecorder || !MediaRecorder.isTypeSupported) return "";
  return ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"]
    .find((type) => MediaRecorder.isTypeSupported(type)) || "";
}

async function startRecording() {
  if (state.busy || state.rec) return;
  unlockAudio();
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || !window.MediaRecorder) {
    toast(t("web_mic_missing"), 5000);
    el.input.focus();
    return;
  }
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
    });
  } catch (err) {
    const blocked = err && (err.name === "NotAllowedError" || err.name === "SecurityError");
    toast(t(blocked ? "web_mic_denied" : "web_mic_missing"), 6000);
    el.input.focus();
    return;
  }
  stopSpeech();
  const mimeType = pickMimeType();
  const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
  const rec = { recorder, stream, chunks: [], started: performance.now(), cancelled: false };
  state.rec = rec;
  recorder.addEventListener("dataavailable", (event) => { if (event.data && event.data.size) rec.chunks.push(event.data); });
  recorder.addEventListener("stop", () => finishRecording(rec));
  recorder.start(250);
  showRecorder(rec);
}

function showRecorder(rec) {
  el.recorder.hidden = false;
  document.body.style.overflow = "hidden";
  $("#recStop").focus();
  const canvas = el.wave;
  const ctx = canvas.getContext("2d");
  const color = getComputedStyle(document.documentElement).getPropertyValue("--primary").trim() || "#12804E";
  let analyser = null;
  try {
    rec.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    analyser = rec.audioCtx.createAnalyser();
    analyser.fftSize = 256;
    rec.audioCtx.createMediaStreamSource(rec.stream).connect(analyser);
  } catch (e) { analyser = null; }
  const data = analyser ? new Uint8Array(analyser.frequencyBinCount) : null;
  const bars = 48;
  const draw = () => {
    if (state.rec !== rec) return;
    const elapsed = (performance.now() - rec.started) / 1000;
    el.recTime.textContent = `${Math.floor(elapsed / 60)}:${String(Math.floor(elapsed % 60)).padStart(2, "0")}`;
    if (elapsed >= MAX_RECORDING_S) { stopRecording(false); return; }
    const { width, height } = canvas;
    ctx.clearRect(0, 0, width, height);
    if (data) analyser.getByteFrequencyData(data);
    const gap = 6;
    const w = (width - gap * (bars - 1)) / bars;
    for (let i = 0; i < bars; i++) {
      const v = data ? data[Math.floor((i / bars) * data.length * 0.7)] / 255 : 0.15 + 0.1 * Math.sin(elapsed * 6 + i);
      const h = Math.max(6, v * height * 0.95);
      ctx.fillStyle = color;
      ctx.globalAlpha = 0.35 + v * 0.65;
      const x = i * (w + gap);
      const y = (height - h) / 2;
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(x, y, w, h, w / 2); else ctx.rect(x, y, w, h);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
    rec.frame = requestAnimationFrame(draw);
  };
  draw();
}

function stopRecording(cancel) {
  const rec = state.rec;
  if (!rec) return;
  rec.cancelled = cancel;
  rec.duration = (performance.now() - rec.started) / 1000;
  cancelAnimationFrame(rec.frame);
  if (rec.recorder.state !== "inactive") rec.recorder.stop();
  rec.stream.getTracks().forEach((track) => track.stop());
  if (rec.audioCtx) rec.audioCtx.close().catch(() => {});
  state.rec = null;
  el.recorder.hidden = true;
  document.body.style.overflow = "";
}

function finishRecording(rec) {
  if (rec.cancelled) return;
  const type = (rec.recorder.mimeType || rec.chunks[0]?.type || "audio/webm");
  const blob = new Blob(rec.chunks, { type });
  if (rec.duration < 0.8 || blob.size < 1200) {
    toast(t("web_too_short"));
    return;
  }
  askByVoice(blob);
}

// ── Theme, install, offline ──────────────────────────────────────────────────
function currentTheme() {
  return document.documentElement.dataset.theme
    || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
}
function renderThemeIcon() {
  el.themeBtn.querySelector("use").setAttribute("href", currentTheme() === "dark" ? "#i-sun" : "#i-moon");
}

// Keep the conversation clear of the dock as it grows (quick replies, long text).
function syncDock() {
  document.documentElement.style.setProperty("--dock-h", `${el.dock.offsetHeight}px`);
}

// ── Wiring ───────────────────────────────────────────────────────────────────
function wire() {
  $("#composer").addEventListener("submit", (event) => {
    event.preventDefault();
    const text = el.input.value;
    el.input.value = "";
    autosize();
    ask(text);
  });
  const autosize = () => {
    el.input.style.height = "auto";
    el.input.style.height = `${Math.min(el.input.scrollHeight, 132)}px`;
    updateSend();
    syncDock();
  };
  el.input.addEventListener("input", autosize);
  el.input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      $("#composer").requestSubmit();
    }
  });

  el.mic.addEventListener("click", startRecording);
  el.orb.addEventListener("click", startRecording);
  $("#recStop").addEventListener("click", () => stopRecording(false));
  $("#recCancel").addEventListener("click", () => stopRecording(true));
  document.addEventListener("keydown", (event) => { if (event.key === "Escape" && state.rec) stopRecording(true); });

  $("#examples").addEventListener("click", (event) => {
    const chip = event.target.closest("[data-q]");
    if (chip) { unlockAudio(); ask(chip.dataset.q, { fresh: true }); }
  });
  el.quick.addEventListener("click", (event) => {
    const chip = event.target.closest("[data-i]");
    if (chip) { unlockAudio(); onQuick(el.quick._chips[Number(chip.dataset.i)]); }
  });

  el.langBtn.addEventListener("click", () => openLanguageSheet(false));
  el.langDialog.addEventListener("click", (event) => { if (event.target === el.langDialog) el.langDialog.close(); });

  el.placeBtn.addEventListener("click", () => openPlaceSheet());
  $("#placeCancel").addEventListener("click", () => el.placeDialog.close());
  el.placeDialog.addEventListener("click", (event) => { if (event.target === el.placeDialog) el.placeDialog.close(); });
  $("#placeForm").addEventListener("submit", (event) => {
    event.preventDefault();
    setPlace(el.placeInput.value);
    el.placeDialog.close();
    const then = el.placeDialog._then;
    el.placeDialog._then = null;
    if (then && state.place) then();
  });
  $("#gpsBtn").addEventListener("click", async () => {
    const button = $("#gpsBtn");
    button.disabled = true;
    try {
      el.placeInput.value = await locate();
      $("#placeSave").focus();
    } catch (e) {
      toast(t("web_gps_failed"));
    } finally {
      button.disabled = false;
    }
  });

  el.newBtn.addEventListener("click", newConversation);
  el.themeBtn.addEventListener("click", () => {
    const next = currentTheme() === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    store.set("ag_theme", next);
    renderThemeIcon();
  });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", renderThemeIcon);

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    state.installPrompt = event;
    el.installBtn.hidden = false;
  });
  el.installBtn.addEventListener("click", async () => {
    if (!state.installPrompt) return;
    state.installPrompt.prompt();
    await state.installPrompt.userChoice.catch(() => null);
    state.installPrompt = null;
    el.installBtn.hidden = true;
  });
  window.addEventListener("offline", () => toast(t("web_offline"), 5000));
  document.addEventListener("pointerdown", unlockAudio, { once: true });

  new ResizeObserver(syncDock).observe(el.dock);
  syncDock();
  renderThemeIcon();
}

async function loadConfig() {
  for (let attempt = 0; attempt < 5; attempt++) {
    try {
      const response = await fetch("/api/config", { cache: "no-store" });
      if (response.ok) return await response.json();
    } catch (e) { /* the server may still be waking up */ }
    await new Promise((resolve) => setTimeout(resolve, 1500 * (attempt + 1)));
  }
  throw new Error("config");
}

async function boot() {
  wire();
  const slow = setTimeout(() => toast("Waking up the assistant — this can take up to a minute…", 60000), 3500);
  try {
    state.config = await loadConfig();
  } catch (e) {
    clearTimeout(slow);
    toast("The assistant is not reachable right now. Please check your internet and reload.", 60000);
    return;
  }
  clearTimeout(slow);
  el.toast.classList.remove("is-on");

  if (!state.config.voice) {
    el.mic.hidden = true;
    el.orb.hidden = true;
  }
  renderLanguageSwitch();
  // A shared link can pick the language: …/?lang=hi opens in Hindi.
  const fromLink = new URLSearchParams(location.search).get("lang");
  const saved = store.get("ag_lang");
  applyLanguage(LOCALES[fromLink] ? fromLink : saved || guessLanguage());
  if (!saved && !LOCALES[fromLink]) openLanguageSheet(true);

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }
}

boot();
