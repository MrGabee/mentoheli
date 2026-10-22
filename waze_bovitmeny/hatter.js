// A bővítmény háttere: a nyitott Waze-fülön a térképet sorban Budapest
// csempéire viszi (a Waze egy nézetre kb. 200 riasztást ad, ezért egy nézet
// nem elég; BETOLTES_KOZ_PERC percenként egy csempe). Az oldalt csak egyszer
// tölti be, utána egérhúzással mozgatja a térképet, mert a sok oldalbetöltés
// 429-et hozott. A térkép által betöltött riasztásokból kiválogatja az újakat,
// és elküldi őket az Apps Scriptnek, ami mindet beírja egy Google Táblázatba,
// és a balesetekről e-mailt is küld.

const BBOX = { left: 18.90, bottom: 47.35, right: 19.35, top: 47.62 }; // Budapest
const TIPUSOK = ["ACCIDENT"];  // ezekről megy levél (a táblázatba minden típus bekerül)
const MEGORZES_MS = 3 * 24 * 3600 * 1000;  // ennyi ideig emlékszik egy riasztásra
const FRISS_MS = 30 * 60 * 1000;           // ennél hosszabb kiesés után újra csak feltölt
const MAX_SZUNET_PERC = 30;
const FRISS_RIASZTAS_MS = 15 * 60 * 1000;  // az első körben is levél megy, ha ennél frissebb a bejelentés
const ZOOM = 13;          // az alap csempék nagyítása (a teljes nézet kb. 12 lenne)
const MAX_ZOOM = 16;      // eddig felezhető egy csempe
const PLAFON = 195;       // ennyi riasztásnál a csempe eléri a Waze ~200-as határát: felezzük
const OSSZEVONAS = 100;   // ha a négy negyed együtt ennyinél kevesebbet ad, újra egy csempe lesz
const PAROSITAS_MS = 30 * 1000;  // ennyi ideig tartozik egy válasz az utoljára betöltött csempéhez
const BETOLTES_KOZ_PERC = 3;  // ennyi percenként tölt be egy csempét (1 percnél is jött 429)
const BETOLTES_PERCENKENT = 1;
const SZORAS_MS = 25 * 1000;  // véletlen késleltetés a betöltés előtt, hogy ne pontosan percre jöjjenek
const VALASZ_VARAS_MS = 18 * 1000;  // ha ennyi idő alatt nem jön adat, az oldal nem töltött be
const MAX_NAGYITAS_LEPES = 2;  // ennél nagyobb nagyításváltáshoz inkább újratölt

// Az alap csempék a Waze-ablak méretéből: annyi nézet, hogy lefedje Budapestet.
// Egy csempe: { id, lat, lon, z, dlat, dlon } (dlat/dlon: a lefedett terület mérete).
function csempek(szel, mag) {
  const lonPx = 360 / (256 * 2 ** ZOOM);
  const latPx = lonPx * Math.cos(((BBOX.bottom + BBOX.top) / 2) * Math.PI / 180);
  const oszlop = Math.max(1, Math.ceil((BBOX.right - BBOX.left) / (szel * lonPx * 0.95)));
  const sor = Math.max(1, Math.ceil((BBOX.top - BBOX.bottom) / (mag * latPx * 0.95)));
  const ki = [];
  for (let i = 0; i < sor; i++) {
    for (let j = 0; j < oszlop; j++) {
      ki.push({
        id: `${i}.${j}`,
        lat: +(BBOX.bottom + (i + 0.5) * (BBOX.top - BBOX.bottom) / sor).toFixed(5),
        lon: +(BBOX.left + (j + 0.5) * (BBOX.right - BBOX.left) / oszlop).toFixed(5),
        z: ZOOM,
        dlat: (BBOX.top - BBOX.bottom) / sor,
        dlon: (BBOX.right - BBOX.left) / oszlop,
      });
    }
  }
  return ki;
}

// Egy csempe négy negyede, eggyel nagyobb nagyítással.
function negyedek(c) {
  const ki = [];
  for (const [i, a] of [[0, -1], [1, 1]]) {
    for (const [j, b] of [[0, -1], [1, 1]]) {
      ki.push({
        id: `${c.id}.${i * 2 + j}`,
        lat: +(c.lat + a * c.dlat / 4).toFixed(5),
        lon: +(c.lon + b * c.dlon / 4).toFixed(5),
        z: c.z + 1, dlat: c.dlat / 2, dlon: c.dlon / 2,
      });
    }
  }
  return ki;
}

// A csempelista (a felezésekkel együtt) megmarad; ablakméret-változáskor újraépül.
async function csempeLista() {
  const { ablak = { szel: 1900, mag: 900 }, lista, listaAblak } =
    await chrome.storage.local.get(["ablak", "lista", "listaAblak"]);
  const kulcs = `${ablak.szel}x${ablak.mag}`;
  if (lista && lista.length && listaAblak === kulcs) return lista;
  const uj = csempek(ablak.szel, ablak.mag);
  await chrome.storage.local.set({ lista: uj, listaAblak: kulcs, mutato: 0 });
  return uj;
}

// Egy csempe betöltése után: ha elérte a határt, négyfelé osztjuk; ha a
// negyedek együtt is keveset adnak, visszavonjuk őket egy csempévé.
function csempeIgazitas(lista, id, darab) {
  const i = lista.findIndex((c) => c.id === id);
  if (i < 0) return { lista, valtozas: "" };
  const c = { ...lista[i], utolso: darab };
  lista = lista.slice();
  lista[i] = c;
  if (darab >= PLAFON && c.z < MAX_ZOOM) {
    lista.splice(i, 1, ...negyedek(c));
    return { lista, valtozas: `csempe ${c.id} négyfelé osztva (${darab} riasztás)`, kovetkezo: i };
  }
  if (c.z > ZOOM) {
    const szulo = c.id.slice(0, c.id.lastIndexOf("."));
    const testverek = lista.filter((t) => t.id.slice(0, t.id.lastIndexOf(".")) === szulo && t.z === c.z);
    if (testverek.length === 4 && testverek.every((t) => t.utolso != null) &&
        testverek.reduce((o, t) => o + t.utolso, 0) < OSSZEVONAS) {
      const elso = lista.findIndex((t) => testverek.includes(t));
      const lat = testverek.reduce((o, t) => o + t.lat, 0) / 4;
      const lon = testverek.reduce((o, t) => o + t.lon, 0) / 4;
      const egy = { id: szulo, lat: +lat.toFixed(5), lon: +lon.toFixed(5), z: c.z - 1, dlat: c.dlat * 2, dlon: c.dlon * 2 };
      lista = lista.filter((t) => !testverek.includes(t));
      lista.splice(elso, 0, egy);
      return { lista, valtozas: `csempe ${szulo} negyedei összevonva`, kovetkezo: elso + 1 };
    }
  }
  return { lista, valtozas: "" };
}

const varj = (ms) => new Promise((r) => setTimeout(r, ms));

// Web Mercator képpont az adott nagyításon (a húzás hosszához).
function kepont(lat, lon, z) {
  const w = 256 * 2 ** z, s = Math.sin(lat * Math.PI / 180);
  return { x: (lon + 180) / 360 * w, y: (0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI)) * w };
}

// A georss kérés a térkép látható területére szól: ennek a közepe.
function kozepe(url) {
  try {
    const p = new URL(url, "https://www.waze.com").searchParams;
    if (!["top", "bottom", "left", "right"].every((k) => p.has(k))) return null;
    const lat = (+p.get("top") + +p.get("bottom")) / 2, lon = (+p.get("left") + +p.get("right")) / 2;
    return isNaN(lat) || isNaN(lon) ? null : { lat, lon };
  } catch (e) {
    return null;
  }
}

const rajta = (k, c) => Math.abs(k.lat - c.lat) < c.dlat / 4 && Math.abs(k.lon - c.lon) < c.dlon / 4;

async function parancs(tabId, p) {
  try {
    const v = await chrome.tabs.sendMessage(tabId, { tipus: "parancs", parancs: p });
    return !!(v && v.ok);
  } catch (e) {
    return false;
  }
}

// A térképet a jelenlegi nézetből (n) a c csempére viszi: előbb dupla
// kattintással a jó nagyításra, aztán egy húzással a helyére.
async function mozgat(tabId, n, c) {
  for (let z = n.z; z !== c.z; z += Math.sign(c.z - z)) {
    if (!await parancs(tabId, { tipus: "nagyit", ki: c.z < z })) return false;
    await varj(2500);
  }
  const a = kepont(n.lat, n.lon, c.z), b = kepont(c.lat, c.lon, c.z);
  return parancs(tabId, { tipus: "huz", dx: Math.round(a.x - b.x), dy: Math.round(a.y - b.y) });
}

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
  kuldesUjraprobalas();  // a sorban fut, nem várjuk meg
  // Csak BETOLTES_KOZ_PERC percenként töltünk be (az időzítő percenként fut).
  const { utolsoBetoltes = 0 } = await chrome.storage.local.get("utolsoBetoltes");
  if (Date.now() - utolsoBetoltes < BETOLTES_KOZ_PERC * 60000 - 20000) return;
  await chrome.storage.local.set({ utolsoBetoltes: Date.now() });
  await varj(Math.random() * SZORAS_MS);
  for (let k = 0; k < BETOLTES_PERCENKENT; k++) {
    const { szunetIg: sz = 0 } = await chrome.storage.local.get("szunetIg");
    if (Date.now() < sz) return;  // a Waze lassítást kért
    const lista = await csempeLista();
    const { mutato = 0 } = await chrome.storage.local.get("mutato");
    const m = mutato % lista.length;
    // Új csempekör: a kijelzés innen számol.
    if (m === 0) await chrome.storage.local.set({ kor: {}, korCsempek: lista.length });
    const c = lista[m];
    const tab = fulek[0];
    const indulas = Date.now();
    await chrome.storage.local.set({ aktualis: { id: c.id, ido: indulas, max: 0 }, mutato: m + 1 });
    // Ha az oldal már be van töltve, csak odahúzzuk a térképet; újratölteni
    // csak az első alkalommal, nagy nagyításváltásnál vagy sikertelen húzás után kell.
    const { nezet } = await chrome.storage.local.get("nezet");
    let huzas = !!nezet && nezet.tab === tab.id && !nezet.ujratolt && /live-map/.test(tab.url || "") &&
      Math.abs(c.z - nezet.z) <= MAX_NAGYITAS_LEPES;
    if (huzas) huzas = await mozgat(tab.id, nezet, c);
    if (huzas) {
      await chrome.storage.local.set({ nezet: { ...(await chrome.storage.local.get("nezet")).nezet, z: c.z } });
    } else {
      await chrome.storage.local.set({ nezet: { tab: tab.id, z: c.z, lat: c.lat, lon: c.lon } });
      const url = `https://www.waze.com/ul?ll=${c.lat}%2C${c.lon}&navigate=no&zoom=${c.z}`;
      try { await chrome.tabs.update(tab.id, { url }); } catch (e) { return; }
    }
    await varj(VALASZ_VARAS_MS);
    const { utolsoValasz = 0, nezet: most } = await chrome.storage.local.get(["utolsoValasz", "nezet"]);
    if (huzas && (utolsoValasz < indulas || !rajta(most, c))) {
      // A húzás nem vitte oda a térképet: legközelebb újratöltéssel megy.
      await chrome.storage.local.set({
        nezet: { ...most, ujratolt: true },
        allapot: `${new Date().toLocaleTimeString("hu-HU")}: a térkép húzása nem sikerült, a következő csempét újratöltéssel nyitja meg.`,
      });
      return;
    }
    // Ha a térkép nem kért adatot, az oldal nem töltött be (pl. 429 az oldalra).
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
chrome.runtime.onMessage.addListener((uz, kuldo) => {
  if (uz && uz.tipus === "georss") sor = sor.then(() => feldolgoz(uz, kuldo.tab && kuldo.tab.id)).catch((e) => console.error(e));
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
      megbizhatosag: a.reliability ?? "",
      megerositesek: a.nThumbsUp ?? 0,
    });
  }
  return ki;
}

async function feldolgoz({ status, adat, url }, tabId) {
  const most = Date.now();
  const t = await chrome.storage.local.get(["latott", "utolsoSiker", "feltoltesIg", "hibaSorozat", "kor", "korUj", "korEmail", "korCsempek", "korMax", "aktualis", "lista", "csempeValtozas", "nezet"]);
  const ido = new Date().toLocaleTimeString("hu-HU");

  // A térkép valódi helye a kérésből: a következő húzás innen számol.
  const kozep = url ? kozepe(url) : null;
  const nezet = t.nezet && t.nezet.tab === tabId && kozep ? { ...t.nezet, ...kozep } : t.nezet;
  await chrome.storage.local.set({ utolsoValasz: most, nezet });
  if (status !== 200 || !adat) {
    await hiba(`HTTP ${status}`);
    return;
  }

  let latott = t.latott || {};
  let feltoltesIg = t.feltoltesIg || 0;
  if (!Object.keys(latott).length || most - (t.utolsoSiker || 0) > FRISS_MS) {
    // Egy teljes csempekörig csak megjegyez.
    const percek = (t.korCsempek || 6) * BETOLTES_KOZ_PERC;
    feltoltesIg = most + percek * 60000 + 30000;
  }
  const feltolt = most < feltoltesIg;

  const riasztasok = kinyer(adat);
  const uj = riasztasok.filter((r) => !(r.id in latott));
  for (const r of riasztasok) latott[r.id] = most;
  for (const [k, v] of Object.entries(latott)) if (most - v > MEGORZES_MS) delete latott[k];

  // Minden új riasztás a táblázatba megy; levél csak a TIPUSOK-ról. Az első
  // körben (amikor a már fennálló riasztásokat látja először) csak a 15 percen
  // belül bejelentettekről.
  for (const r of uj) {
    r.elso_latva_ms = most;
    const friss = r.bejelentve_ms && most - r.bejelentve_ms < FRISS_RIASZTAS_MS;
    r.level = TIPUSOK.includes(r.tipus) && (!feltolt || friss);
  }
  const emailre = uj.filter((r) => r.level);
  // A térkép egy betöltésnél több részletben kér adatot; a kijelzés a
  // legutóbbi frissítés óta látott összes riasztást mutatja.
  const ujKor = !Object.keys(t.kor || {}).length;
  const kor = t.kor || {};
  for (const r of riasztasok) kor[r.id] = 1;
  const korUj = (ujKor ? 0 : t.korUj || 0) + uj.length;
  const korEmail = (ujKor ? 0 : t.korEmail || 0) + emailre.length;
  const nyers = ((adat && adat.alerts) || []).length;
  const korMax = Math.max(ujKor ? 0 : t.korMax || 0, nyers);
  // A válasz az utoljára betöltött csempéé: ha elérte a határt, felezzük.
  let csempeValtozas = t.csempeValtozas || "";
  const csempeAllapot = {};
  // A válasz csak akkor a csempéé, ha a térkép már ott áll (húzás közben jöhet más nézetről is).
  const aktC = t.aktualis && t.lista && t.lista.find((c) => c.id === t.aktualis.id);
  if (aktC && most - t.aktualis.ido < PAROSITAS_MS && (!kozep || rajta(kozep, aktC))) {
    const darab = Math.max(t.aktualis.max || 0, nyers);
    const ig = csempeIgazitas(t.lista, t.aktualis.id, darab);
    if (ig.valtozas) {
      csempeValtozas = `${ido}: ${ig.valtozas}, most ${ig.lista.length} csempe.`;
      // A felezett/összevont csempe azonosítója megszűnt: a további részválaszok már nem módosítanak.
      csempeAllapot.aktualis = null;
      // A következő betöltés az első negyeddel (összevonás után a következő csempével) folytatódik.
      csempeAllapot.mutato = ig.kovetkezo;
    } else {
      csempeAllapot.aktualis = { ...t.aktualis, max: darab };
    }
    csempeAllapot.lista = ig.lista;
  }
  await chrome.storage.local.set({
    latott, feltoltesIg, utolsoSiker: most, hibaSorozat: 0, szunetIg: 0, kor, korUj, korEmail, korMax,
    ...csempeAllapot, csempeValtozas,
    allapot: `${ido}: ${Object.keys(kor).length} riasztás Budapesten (${t.korCsempek || 1} csempéből, ${BETOLTES_KOZ_PERC} percenként egy), ${korUj} új` +
      (feltolt ? ` (első kör: levél csak a 15 percen belüli balesetekről, most ${korEmail}).` : `, levélben: ${korEmail}.`) +
      `\nLegnagyobb csempe: ${korMax} riasztás` + (korMax >= PLAFON ? " (a csempét felezi)" : ".") +
      (csempeValtozas ? `\nUtolsó csempeváltozás: ${csempeValtozas}` : ""),
  });
  if (uj.length) await kuldes(uj);
}

// --- Küldés az Apps Scriptnek --------------------------------------------
// A küldendő riasztások előbb a tárolt sorba kerülnek, és csak sikeres küldés
// után törlődnek onnan, így egy hiba vagy a háttér leállása sem veszít el semmit.
async function kuldes(riasztasok, teszt = false) {
  const { scriptUrl, titok, kuldendo = [] } = await chrome.storage.local.get(["scriptUrl", "titok", "kuldendo"]);
  const csomag = teszt ? riasztasok : kuldendo.concat(riasztasok).slice(-3000);
  if (!teszt) await chrome.storage.local.set({ kuldendo: csomag });
  if (!csomag.length) return;
  if (!scriptUrl) {
    await chrome.storage.local.set({ levelAllapot: "Nincs megadva Apps Script URL." });
    return;
  }
  const ido = new Date().toLocaleTimeString("hu-HU");
  const megszakito = new AbortController();
  const idozites = setTimeout(() => megszakito.abort(), 60000);
  try {
    const v = await fetch(scriptUrl, {
      method: "POST",
      headers: { "Content-Type": "text/plain;charset=utf-8" },
      body: JSON.stringify({ titok: titok || "", teszt, riasztasok: csomag }),
      signal: megszakito.signal,
    });
    const szoveg = await v.text();
    if (!v.ok || !szoveg.startsWith("OK")) throw new Error(`${v.status} ${szoveg.slice(0, 80)}`);
    const elkuldve = new Set(csomag.map((r) => r.id));
    const { kuldendo: most = [] } = await chrome.storage.local.get("kuldendo");
    await chrome.storage.local.set({
      ...(teszt ? {} : { kuldendo: most.filter((r) => !elkuldve.has(r.id)) }),
      levelAllapot: teszt ? `${ido}: teszt e-mail elküldve.`
        : `${ido}: ${csomag.length} riasztás a táblázatba, ebből ${csomag.filter((r) => r.level).length} levélben.`,
    });
  } catch (e) {
    await chrome.storage.local.set({
      levelAllapot: `${ido}: küldési hiba (később újrapróbálja): ${e.name === "AbortError" ? "időtúllépés" : e.message}`,
    });
  } finally {
    clearTimeout(idozites);
  }
}

// Az újrapróbálás is a feldolgozási sorba áll, hogy ne fusson egyszerre két küldés.
function kuldesUjraprobalas() {
  sor = sor.then(async () => {
    const { kuldendo = [] } = await chrome.storage.local.get("kuldendo");
    if (kuldendo.length) await kuldes([]);
  }).catch((e) => console.error(e));
  return sor;
}

async function tesztLevel() {
  await kuldes([{
    id: "teszt", tipus: "ACCIDENT", altipus: "ACCIDENT_MINOR", utca: "Teszt utca", varos: "Budapest",
    leiras: "Ez egy teszt levél a bővítményből.", lat: 47.4979, lon: 19.0402, bejelentve_ms: Date.now(), level: true,
  }], true);
}
