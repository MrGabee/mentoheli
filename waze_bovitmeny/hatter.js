// A bővítmény háttere: percenként frissíti a nyitott Waze-fület, a térkép
// által betöltött riasztásokból kiválogatja az újakat, és elküldi őket az
// Apps Scriptnek, ami e-mailt küld róluk.

const BBOX = { left: 18.90, bottom: 47.35, right: 19.35, top: 47.62 }; // Budapest
const TIPUSOK = ["ACCIDENT"];  // csak balesetekről megy levél
const MEGORZES_MS = 3 * 24 * 3600 * 1000;  // ennyi ideig emlékszik egy riasztásra
const FRISS_MS = 30 * 60 * 1000;           // ennél hosszabb kiesés után újra csak feltölt
const FELTOLTES_MS = 20 * 1000;            // a feltöltő kör ennyi ideig tart
const MAX_SZUNET_PERC = 15;

// --- Időzítő -------------------------------------------------------------
function idozito() {
  chrome.alarms.create("frissites", { periodInMinutes: 1 });
}
chrome.runtime.onInstalled.addListener(idozito);
chrome.runtime.onStartup.addListener(idozito);

chrome.alarms.onAlarm.addListener(async (a) => {
  if (a.name !== "frissites") return;
  const { szunetIg = 0 } = await chrome.storage.local.get("szunetIg");
  if (Date.now() < szunetIg) return;
  const fulek = await chrome.tabs.query({ url: "https://www.waze.com/*live-map*" });
  if (!fulek.length) {
    await chrome.storage.local.set({ allapot: "Nincs nyitott Waze Live Map fül." });
    return;
  }
  await chrome.storage.local.set({ kor: {} });  // ebben a körben látott riasztások
  chrome.tabs.reload(fulek[0].id);
  await kuldesUjraprobalas();
});

// --- Válaszok feldolgozása (egymás után, hogy ne akadjanak össze) --------
let sor = Promise.resolve();
chrome.runtime.onMessage.addListener((uz) => {
  if (uz && uz.tipus === "georss") sor = sor.then(() => feldolgoz(uz)).catch((e) => console.error(e));
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
  const t = await chrome.storage.local.get(["latott", "utolsoSiker", "feltoltesIg", "hibaSorozat", "kor", "korUj", "korEmail"]);
  const ido = new Date().toLocaleTimeString("hu-HU");

  if (status !== 200 || !adat) {
    const hiba = (t.hibaSorozat || 0) + 1;
    const perc = Math.min(2 ** hiba, MAX_SZUNET_PERC);
    await chrome.storage.local.set({
      hibaSorozat: hiba,
      szunetIg: most + perc * 60000,
      allapot: `${ido}: HTTP ${status}, ${perc} perc szünet.`,
    });
    return;
  }

  let latott = t.latott || {};
  let feltoltesIg = t.feltoltesIg || 0;
  if (!Object.keys(latott).length || most - (t.utolsoSiker || 0) > FRISS_MS) {
    feltoltesIg = most + FELTOLTES_MS;
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
  await chrome.storage.local.set({
    latott, feltoltesIg, utolsoSiker: most, hibaSorozat: 0, szunetIg: 0, kor, korUj, korEmail,
    allapot: `${ido}: ${Object.keys(kor).length} riasztás a térképen, ${korUj} új` +
      (feltolt ? " (első kör: csak megjegyezve)." : `, levélben: ${korEmail}.`),
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
