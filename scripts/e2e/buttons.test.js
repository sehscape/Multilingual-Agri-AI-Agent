// Every button of the web app, pressed in a real Chrome, each checked for the
// job it is meant to do.
//
//   npm install                                   # playwright-core (uses your installed Chrome)
//   python scripts/make_voice_sample.py           # optional: a spoken question for the mic tests
//   python app.py                                 # in another terminal
//   npm run test:e2e -- http://127.0.0.1:7860/    # or any deployed URL
//
// CHROME_PATH=/path/to/chrome picks a browser explicitly. The voice checks need
// a Groq key on the server and scripts/e2e/question_hi.wav; without them they
// are skipped, not failed.
"use strict";

const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright-core");

const url = process.argv[2] || process.env.APP_URL || "http://127.0.0.1:7860/";
const voiceWav = path.join(__dirname, "question_hi.wav");
const haveWav = fs.existsSync(voiceWav);

let passes = 0, fails = 0, skips = 0;
function check(label, ok, extra = "") {
  console.log(`[${ok ? "PASS" : "FAIL"}] ${label}${extra && !ok ? "  — " + String(extra).replace(/\s+/g, " ").slice(0, 110) : ""}`);
  if (ok) passes++; else fails++;
}
function skip(label, why) { console.log(`[SKIP] ${label} — ${why}`); skips++; }

const bots = (p) => p.locator(".msg--bot");
const lastBot = (p) => bots(p).last();
async function waitAnswer(p) {
  for (let k = 0; k < 40 && !(await p.locator(".typing").count()); k++) await p.waitForTimeout(150);
  for (let k = 0; k < 360 && await p.locator(".typing").count(); k++) await p.waitForTimeout(250);
  await p.waitForTimeout(600);
}
const brand = (p) => p.locator(".brand-name").innerText();
const isOpen = (p, id) => p.locator(id).evaluate((d) => d.open);

(async () => {
  const args = ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
                "--autoplay-policy=no-user-gesture-required"];
  if (haveWav) args.push(`--use-file-for-fake-audio-capture=${voiceWav}`);
  const browser = await chromium.launch(process.env.CHROME_PATH
    ? { executablePath: process.env.CHROME_PATH, args } : { channel: "chrome", args });
  const ctx = await browser.newContext({
    viewport: { width: 1280, height: 900 },
    permissions: ["microphone", "geolocation", "clipboard-read", "clipboard-write"],
    geolocation: { latitude: 18.5204, longitude: 73.8567 },
  });
  const p = await ctx.newPage();
  const errors = [];
  p.on("pageerror", (e) => errors.push(e.message));
  p.on("console", (m) => { if (m.type() === "error" && !/Failed to load resource/.test(m.text())) errors.push(m.text()); });
  await p.goto(url, { waitUntil: "load" });
  await p.waitForFunction(() => document.querySelector("#bento .tile"), null, { timeout: 120000 });
  const voiceOn = await p.evaluate(() => !document.querySelector("#micBtn").hidden);

  // ── Language ──
  check("first visit opens the language sheet", await isOpen(p, "#langDialog"));
  await p.locator('#langGrid button[data-lang="hi"]').click();
  await p.waitForTimeout(300);
  check("language sheet → Hindi: the whole page switches", (await brand(p)).includes("कृषि") && !(await isOpen(p, "#langDialog")));
  if (voiceOn) check("mic labelled in Hindi", (await p.locator(".orb-label").innerText()).includes("बोलने"));
  await p.locator('#langs button[data-lang="en"]').click();
  check("language switch → English", (await brand(p)) === "Agri Assistant"
        && (await p.locator('#langs button[data-lang="en"]').getAttribute("aria-checked")) === "true");

  // ── Theme ──
  const before = await p.evaluate(() => document.documentElement.dataset.theme || "auto");
  await p.locator("#themeBtn").click();
  const after = await p.evaluate(() => document.documentElement.dataset.theme);
  check("theme button switches light/dark", after && after !== before, `${before} → ${after}`);
  await p.locator("#themeBtn").click();

  // ── Village sheet ──
  await p.locator("#placeBtn").click();
  check("village button opens the sheet", await isOpen(p, "#placeDialog"));
  await p.locator("#placeInput").fill("Somewhere");
  await p.locator("#placeCancel").click();
  check("Cancel closes without saving", !(await isOpen(p, "#placeDialog"))
        && !(await p.locator("#placeLabel").innerText()).includes("Somewhere"));
  await p.locator("#placeBtn").click();
  await p.locator("#gpsBtn").click();
  await p.waitForTimeout(800);
  check("📍 in the sheet fills the GPS position", /18\.52\d*, 73\.85/.test(await p.locator("#placeInput").inputValue()));
  await p.locator("#placeInput").fill("Nashik");
  await p.locator("#placeSave").click();
  check("Save sets the village", (await p.locator("#placeLabel").innerText()) === "Nashik"
        && (await p.evaluate(() => localStorage.getItem("ag_place"))) === "Nashik");

  // ── An example question ──
  await p.locator("#examples .chip").nth(0).click();
  await waitAnswer(p);
  check("example card asks and gets an answer", (await bots(p).count()) === 1
        && (await lastBot(p).locator(".bubble-bot").innerText()).length > 20);
  check("welcome hides, New conversation appears", await p.locator("#welcome").isHidden() && await p.locator("#newBtn").isVisible());

  // ── Listen / Copy / WhatsApp / details ──
  await p.waitForTimeout(3000);
  const listen = lastBot(p).locator(".act--listen");
  const l1 = await listen.locator("span").innerText();
  await listen.click(); await p.waitForTimeout(300);
  const l2 = await listen.locator("span").innerText();
  await listen.click(); await p.waitForTimeout(600);
  const l3 = await listen.locator("span").innerText();
  check("Listen: plays by itself, pauses, resumes", l1 === "Pause" && l2 === "Listen" && l3 === "Pause", `${l1} → ${l2} → ${l3}`);

  await lastBot(p).locator('[data-act="copy"]').click();
  await p.waitForTimeout(300);
  const clip = await p.evaluate(() => navigator.clipboard.readText());
  check("Copy puts the answer on the clipboard", clip.length > 20, clip.slice(0, 60));

  const [popup] = await Promise.all([p.waitForEvent("popup", { timeout: 15000 }),
                                     lastBot(p).locator('[data-act="share"]').click()]);
  check("WhatsApp opens a share link carrying the answer", /whatsapp\.com/.test(popup.url()) && /text=/.test(popup.url()), popup.url());
  await popup.close();

  await lastBot(p).locator('[data-act="details"]').click();
  const shown = await lastBot(p).locator(".details").count();
  await lastBot(p).locator('[data-act="details"]').click();
  check("ⓘ shows and hides how the answer was made", shown === 1 && (await lastBot(p).locator(".details").count()) === 0);

  // ── Composer + ask-back quick replies ──
  check("Send is disabled while the box is empty", await p.locator("#sendBtn").isDisabled());
  await p.locator("#input").fill("When should I put fertilizer in my wheat?");
  check("typing enables Send", await p.locator("#sendBtn").isEnabled());
  await p.locator("#input").press("Enter");
  await waitAnswer(p);
  const chips = await p.locator("#quick .chip").allInnerTexts();
  check("Enter sends; the ask-back offers one-tap ages", chips.includes("40 days"), chips.join(" | "));
  await p.locator("#quick .chip", { hasText: "40 days" }).click();
  await waitAnswer(p);
  check('one-tap "40 days" completes the question → crop-stage card',
        (await lastBot(p).locator(".card--crop").count()) === 1 && (await p.locator("#quick .chip").count()) === 0);

  // ── No village → 📍 chip asks again for the GPS position ──
  await p.locator("#placeBtn").click(); await p.locator("#placeInput").fill(""); await p.locator("#placeSave").click();
  await p.locator("#input").fill("Will it rain tomorrow?");
  await p.locator("#sendBtn").click();
  await waitAnswer(p);
  const loc = await p.locator("#quick .chip").allInnerTexts();
  check("no village → asks where, offers 📍 and a village chip", loc.some((c) => /location/i.test(c)), loc.join(" | "));
  await p.locator("#quick .chip").first().click();
  await waitAnswer(p);
  check("📍 chip asks the same question for the GPS position → weather card", (await lastBot(p).locator(".card--weather").count()) === 1);

  // ── A failure, then Retry ──
  await p.route("**/api/ask", (route) => route.fulfill({ status: 500, contentType: "application/json", body: '{"error":"test failure"}' }), { times: 1 });
  await p.locator("#input").fill("How do I apply for PM-KISAN?");
  await p.locator("#sendBtn").click();
  await waitAnswer(p);
  const failed = await lastBot(p).locator(".is-error").count();
  await lastBot(p).locator(".actions button").click();
  await waitAnswer(p);
  check("a failed answer offers Retry, and Retry works", failed === 1 && (await lastBot(p).locator(".card--scheme").count()) === 1);

  // ── Voice ──
  if (!voiceOn) {
    skip("voice: mic, stop, spoken question answered", "the server has no speech service (no Groq key)");
  } else {
    await p.locator('#langs button[data-lang="hi"]').click();
    await p.locator("#micBtn").click();
    await p.waitForTimeout(600);
    check("mic opens the recorder with a live timer", await p.locator("#recorder").isVisible());
    if (!haveWav) {
      await p.locator("#recCancel").click();
      skip("voice: a spoken question answered", "run scripts/make_voice_sample.py first");
    } else {
      await p.waitForTimeout(6500);
      await p.locator("#recStop").click();
      check("Stop closes the recorder", await p.locator("#recorder").isHidden());
      await waitAnswer(p);
      const heard = await p.locator(".msg--user .words").last().innerText();
      check("spoken Hindi question heard and answered in Hindi", /[ऀ-ॿ]/.test(heard)
            && /[ऀ-ॿ]/.test(await lastBot(p).locator(".bubble-bot").innerText()), heard);
    }
  }

  // ── New conversation, big mic, Cancel, Esc ──
  await p.locator("#newBtn").click();
  check("New conversation clears the thread", (await bots(p).count()) === 0 && await p.locator("#welcome").isVisible());
  if (voiceOn) {
    await p.locator("#orbBtn").click(); await p.waitForTimeout(800);
    const opened = await p.locator("#recorder").isVisible();
    await p.locator("#recCancel").click(); await p.waitForTimeout(500);
    check("big mic opens the recorder; Cancel discards it", opened && await p.locator("#recorder").isHidden() && (await bots(p).count()) === 0);
    await p.locator("#orbBtn").click(); await p.waitForTimeout(800);
    await p.keyboard.press("Escape"); await p.waitForTimeout(400);
    check("Esc cancels a recording", await p.locator("#recorder").isHidden() && (await bots(p).count()) === 0);
  }

  // ── Phone ──
  await p.setViewportSize({ width: 390, height: 844 });
  await p.waitForTimeout(400);
  await p.locator("#langBtn").click();
  const sheet = await isOpen(p, "#langDialog");
  await p.locator('#langGrid button[data-lang="mr"]').click();
  check("phone: language button opens the sheet → Marathi", sheet && (await p.locator("#langLabel").innerText()) === "मराठी");
  await p.locator("#placeBtn").click();
  check("phone: 📍 opens the village sheet", await isOpen(p, "#placeDialog"));
  await p.locator("#placeCancel").click();
  check("phone: nothing scrolls sideways", (await p.evaluate(() => document.documentElement.scrollWidth)) <= 390);

  // ── Links, install, errors ──
  const link = await ctx.newPage();
  await link.goto(new URL("?lang=pa", url).href, { waitUntil: "load" });
  await link.waitForFunction(() => document.querySelector("#bento .tile"), null, { timeout: 60000 });
  check("a ?lang=pa link opens in Punjabi", (await brand(link)).includes("ਖੇਤੀ"));
  await link.close();
  check("service worker registered (installable, opens offline)",
        await p.evaluate(async () => !!(await navigator.serviceWorker.getRegistration())));
  check("no JavaScript errors", errors.length === 0, errors.join(" || "));

  await browser.close();
  console.log(`\nResult: ${passes} passed, ${fails} failed${skips ? `, ${skips} skipped` : ""}`);
  process.exit(fails ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
