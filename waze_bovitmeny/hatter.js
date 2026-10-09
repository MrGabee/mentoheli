// A bővítmény háttere: a nyitott Waze-fület sorban Budapest csempéire
// navigálja (a Waze egy betöltésre kb. 200 riasztást ad, ezért egy nézet nem
// elég; percenként legfeljebb BETOLTES_PERCENKENT betöltés, hogy ne kapjon 429-et), a térkép által betöltött riasztásokból kiválogatja az újakat, és
// elküldi őket az Apps Scriptnek, ami e-mailt küld róluk.

const BBOX = { left: 18.90, bottom: 47.35, right: 19.35, top: 47.62 }; // Budapest
const TIPUSOK = ["ACCIDENT"];  // csak balesetekről megy levél
const MEGORZES_MS = 3 * 24 * 3600 * 1000;  // ennyi ideig emlékszik egy riasztásra
const FRISS_MS = 30 * 60 * 1000;           // ennél hosszabb kiesés után újra csak feltölt
const MAX_SZUNET_PERC = 30;
const ZOOM = 13;          // csempék nagyítása (a teljes nézet kb. 12 lenne)
const BETOLTES_PERCENKENT = 2;  // ennyi csempét tölt be percenként (6-nál a Waze letiltotta az oldalt)
const VALASZ_VARAS_MS = 18 * 1000;  // ha ennyi idő alatt nem jön adat, az oldal nem töltött be

// A csempék a Waze-ablak méretéből: annyi nézet, hogy lefedje Budapestet.
function csempek(szel, mag) {
  const lonPx = 360 / (256 * 2 ** ZOOM);
  const latPx = lonPx * Math.cos(((BBOX.bottom + BBOX.top) / 2) * Math.PI / 180);
  const oszlop = Math.max(1, Math.ceil((BBOX.right - BBOX.left) / (szel * lonPx * 0.95)));
  const sor = Math.max(1, Math.ceil((BBOX.top - BBOX.bottom) / (mag * latPx * 0.95)));
  const ki = [];
  for (let i = 0; i < sor; i++) {
    for (let j = 0; j < oszlop; j++) {
      ki.push({
        lat: +(BBOX.bottom + (i + 0.5) * (BBOX.top - BBOX.bottom) / sor).toFixed(5),
        lon: +(BBOX.left + (j + 0.5) * (BBOX.right - BBOX.left) / oszlop).toFixed(5),
      });
    }
  }
  return ki;
}

const varj = (ms) => new Promise((r) => setTimeout(r, ms));

// --- Időzítő -------------------------------------------------------------
function idozito() {
  chrome.alarms.create("frissites", { periodInMinutes: 1 });
}
chrome.runtime.onInstalled.addListener(idozito);
chrome.runtime.onStartup.addListener(idozito);

let fut = false;  // egyszerre csak egy betöltési sorozat fusson
chrome.alarms.onAlarm.addListener(async (a) => {
  if (a.name !== "frissites" || fut) return;
  fut = true;
  try { await betoltesek(); } finally { fut = false; }
});

async function betoltesek() {
  const { szunetIg = 0 } = await chrome.storage.local.get("szunetIg");
  if (Date.now() < szunetIg) return;
  const fulek = (await chrome.tabs.query({ url: "https://www.waze.com/*" }))
    .filter((f) => /live-map|\/ul\?/.test(f.url || ""));
  if (!fulek.length) {
    await chrome.storage.local.set({ allapot: "Nincs nyitott Waze Live Map fül." });
    return;
  }
  const { ablak = { szel: 1900, mag: 900 }, mutato = 0 } = await chrome.storage.local.get(["ablak", "mutato"]);
  const lista = csempek(ablak.szel, ablak.mag);
  await kuldesUjraprobalas();
  let m = mutato % lista.length;
  for (let k = 0; k < Math.min(BETOLTES_PERCENKENT, lista.length); k++) {
    const { szunetIg: sz = 0 } = await chrome.storage.local.get("szunetIg");
    if (Date.now() < sz) return;  // a Waze lassítást kért
    // Új csempekör: a kijelzés innen számol.
    if (m === 0) await chrome.storage.local.set({ kor: {}, korCsempek: lista.length });
    const c = lista[m];
    const indulas = Date.now();
    const url = `https://www.waze.com/ul?ll=${c.lat}%2C${c.lon}&navigate=no&zoom=${ZOOM}`;
    try { await chrome.tabs.update(fulek[0].id, { url }); } catch (e) { return; }
    m = (m + 1) % lista.length;
    await chrome.storage.local.set({ mutato: m });
    await varj(VALASZ_VARAS_MS);
    // Ha a térkép nem kért adatot, az oldal nem töltött be (pl. 429 az oldalra).
    const { utolsoValasz = 0 } = await chrome.storage.local.get("utolsoValasz");
    if (utolsoValasz < indulas) {
      await hiba("az oldal nem töltött be (valószínűleg 429)");
      return;
    }
  }
}

async function hiba(ok) {
  const { hibaSorozat = 0 } = await chrome.storage.local.get("hibaSorozat");
  const perc = Math.min(2 ** (hibaSorozat + 1), MAX_SZUNET_PERC);
  await chrome.storage.local.set({
    hibaSorozat: hibaSorozat + 1,
    szunetIg: Date.now() + perc * 60000,
    allapot: `${new Date().toLocaleTimeString("hu-HU")}: ${ok}, ${perc} perc szünet.`,
  });
}

// --- Válaszok feldolgozása (egymás után, hogy ne akadjanak össze) --------
let sor = Promise.resolve();
chrome.runtime.onMessage.addListener((uz) => {
  if (uz && uz.tipus === "georss") sor = sor.then(() => feldolgoz(uz)).catch((e) => console.error(e));
  if (uz && uz.tipus === "ablak") chrome.storage.local.set({ ablak: { szel: uz.szel, mag: uz.mag } });
  if (uz && uz.tipus === "teszt") sor = sor.then(tesztLevel).catch((e) => console.error(e));
});

function bboxban(lat, lon) {
  return lat >= BBOX.bottom && lat <= BBOX.top && lon >= BBOX.left && lon <= BBOX.right;
}

function kinyer(adat) {
  const ki = [];
  for (const a of (adat && adat.alerts) || []) {
    const lat = a.location && a.location.y, lon = a.location && a.location.x;
    if (lat == null || lon == null || !bboxban(lat, lon)) continue;
    ki.push({
      id: String(a.uuid || a.id || `${a.type}|${lat.toFixed(5)}|${lon.toFixed(5)}`),
      tipus: a.type || "ISMERETLEN",
      altipus: a.subtype || "",
      utca: a.street || "",
      varos: a.city || "",
      leiras: a.reportDescription || "",
      lat, lon,
      bejelentve_ms: a.pubMillis || 0,
    });
  }
  return ki;
}

async function feldolgoz({ status, adat }) {
  const most = Date.now();
  const t = await chrome.storage.local.get(["latott", "utolsoSiker", "feltoltesIg", "hibaSorozat", "kor", "korUj", "korEmail", "korCsempek", "korMax"]);
  const ido = new Date().toLocaleTimeString("hu-HU");

  await chrome.storage.local.set({ utolsoValasz: most });
  if (status !== 200 || !adat) {
    await hiba(`HTTP ${status}`);
    return;
  }

  let latott = t.latott || {};
  let feltoltesIg = t.feltoltesIg || 0;
  if (!Object.keys(latott).length || most - (t.utolsoSiker || 0) > FRISS_MS) {
    // Egy teljes csempekörig csak megjegyez.
    const percek = Math.ceil((t.korCsempek || 6) / BETOLTES_PERCENKENT);
    feltoltesIg = most + percek * 60000 + 30000;
  }
  const feltolt = most < feltoltesIg;

  const riasztasok = kinyer(adat);
  const uj = riasztasok.filter((r) => !(r.id in latott));
  for (const r of riasztasok) latott[r.id] = most;
  for (const [k, v] of Object.entries(latott)) if (most - v > MEGORZES_MS) delete latott[k];

  const emailre = feltolt ? [] : uj.filter((r) => TIPUSOK.includes(r.tipus));
  // A térkép egy betöltésnél több részletben kér adatot; a kijelzés a
  // legutóbbi frissítés óta látott összes riasztást mutatja.
  const ujKor = !Object.keys(t.kor || {}).length;
  const kor = t.kor || {};
  for (const r of riasztasok) kor[r.id] = 1;
  const korUj = (ujKor ? 0 : t.korUj || 0) + uj.length;
  const korEmail = (ujKor ? 0 : t.korEmail || 0) + emailre.length;
  const nyers = ((adat && adat.alerts) || []).length;
  const korMax = Math.max(ujKor ? 0 : t.korMax || 0, nyers);
  await chrome.storage.local.set({
    latott, feltoltesIg, utolsoSiker: most, hibaSorozat: 0, szunetIg: 0, kor, korUj, korEmail, korMax,
    allapot: `${ido}: ${Object.keys(kor).length} riasztás Budapesten (${t.korCsempek || 1} csempéből, ${BETOLTES_PERCENKENT}/perc), ${korUj} új` +
      (feltolt ? " (első kör: csak megjegyezve)." : `, levélben: ${korEmail}.`) +
      `\nLegnagyobb csempe: ${korMax} riasztás` + (korMax >= 195 ? " ⚠️ eléri a Waze 200-as határát" : "."),
  });
  if (emailre.length) await kuldes(emailre);
}

// --- Küldés az Apps Scriptnek --------------------------------------------
async function kuldes(riasztasok, teszt = false) {
  const { scriptUrl, titok, kuldendo = [] } = await chrome.storage.local.get(["scriptUrl", "titok", "kuldendo"]);
  const csomag = teszt ? riasztasok : kuldendo.concat(riasztasok).filter((r) => TIPUSOK.includes(r.tipus));
  if (!csomag.length) {
    await chrome.storage.local.set({ kuldendo: [] });
    return;
  }
  if (!scriptUrl) {
    await chrome.storage.local.set({ kuldendo: csomag.slice(-200), levelAllapot: "Nincs megadva Apps Script URL." });
    return;
  }
  const ido = new Date().toLocaleTimeString("hu-HU");
  try {
    const v = await fetch(scriptUrl, {
      method: "POST",
      headers: { "Content-Type": "text/plain;charset=utf-8" },
      body: JSON.stringify({ titok: titok || "", teszt, riasztasok: csomag }),
    });
    const szoveg = await v.text();
    if (!v.ok || !szoveg.startsWith("OK")) throw new Error(`${v.status} ${szoveg.slice(0, 80)}`);
    await chrome.storage.local.set({
      ...(teszt ? {} : { kuldendo: [] }),
      levelAllapot: `${ido}: e-mail elküldve (${csomag.length} esemény).`,
    });
  } catch (e) {
    await chrome.storage.local.set({
      ...(teszt ? {} : { kuldendo: csomag.slice(-200) }),
      levelAllapot: `${ido}: e-mail hiba: ${e.message}`,
    });
  }
}

async function kuldesUjraprobalas() {
  const { kuldendo = [] } = await chrome.storage.local.get("kuldendo");
  if (kuldendo.length) await kuldes([]);
}

async function tesztLevel() {
  await kuldes([{
    id: "teszt", tipus: "ACCIDENT", altipus: "ACCIDENT_MINOR", utca: "Teszt utca", varos: "Budapest",
    leiras: "Ez egy teszt levél a bővítményből.", lat: 47.4979, lon: 19.0402, bejelentve_ms: Date.now(),
  }], true);
}
