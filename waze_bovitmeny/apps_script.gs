// Waze Budapest figyelő - e-mail küldő (Google Apps Script webalkalmazás)
// A Chrome-bővítmény ide küldi az új riasztásokat, ez pedig a Gmailedről
// e-mailt küld róluk. A Waze-t nem olvassa, csak levelet küld.
//
// Beállítás: írd át a TITOK és a CIMZETT értékét, majd
// Telepítés > Új telepítés > Webalkalmazás,
// "Végrehajtás mint: Én", "Hozzáférés: Bárki".

const TITOK = "ide-irj-egy-hosszu-titkos-szot";
const CIMZETT = "ide@a-cimed.hu";

const TIPUSOK = {
  ACCIDENT: ["💥", "Baleset", "#c62828"],
  ROAD_CLOSED: ["⛔", "Útlezárás", "#6a1b9a"],
  POLICE: ["🚓", "Rendőr", "#1565c0"],
  HAZARD: ["⚠️", "Veszély", "#ef6c00"],
  JAM: ["🚗", "Torlódás", "#5d4037"],
};
const ALTIPUSOK = {
  ACCIDENT_MAJOR: "Súlyos baleset",
  ACCIDENT_MINOR: "Kisebb baleset",
  POLICE_VISIBLE: "Látható rendőr",
  POLICE_HIDING: "Rejtett rendőr",
  HAZARD_ON_ROAD_POT_HOLE: "Kátyú",
  HAZARD_ON_ROAD_OBJECT: "Tárgy az úton",
  HAZARD_ON_ROAD_CAR_STOPPED: "Álló jármű az úton",
  HAZARD_ON_SHOULDER_CAR_STOPPED: "Álló jármű a leállósávban",
  HAZARD_ON_ROAD_CONSTRUCTION: "Útépítés",
  HAZARD_ON_ROAD_TRAFFIC_LIGHT_FAULT: "Lámpahiba",
  HAZARD_ON_ROAD_ROAD_KILL: "Elütött állat",
  HAZARD_ON_SHOULDER_ANIMALS: "Állat az út szélén",
  HAZARD_ON_ROAD_ICE: "Jeges út",
  HAZARD_ON_ROAD_LANE_CLOSED: "Sávlezárás",
  HAZARD_WEATHER_FOG: "Köd",
  HAZARD_WEATHER_FLOOD: "Elöntött út",
};
const SORREND = { ACCIDENT: 0, ROAD_CLOSED: 1, POLICE: 2, HAZARD: 3, JAM: 4 };

function doPost(e) {
  let adat;
  try {
    adat = JSON.parse(e.postData.contents);
  } catch (err) {
    return ContentService.createTextOutput("HIBA: rossz adat");
  }
  if (adat.titok !== TITOK) return ContentService.createTextOutput("HIBA: rossz titkos kulcs");
  const riasztasok = adat.riasztasok || [];
  if (riasztasok.length) level(riasztasok, adat.teszt);
  return ContentService.createTextOutput("OK " + riasztasok.length);
}

function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function gomb(url, felirat, szin) {
  return '<a href="' + esc(url) + '" style="display:inline-block;padding:6px 12px;border-radius:6px;' +
    "background:" + szin + ';color:#fff;text-decoration:none;font-size:13px;font-weight:600;white-space:nowrap">' +
    felirat + "</a>";
}

function level(riasztasok, teszt) {
  riasztasok.sort(function (a, b) {
    return ((SORREND[a.tipus] ?? 9) - (SORREND[b.tipus] ?? 9)) || ((b.bejelentve_ms || 0) - (a.bejelentve_ms || 0));
  });
  const most = Utilities.formatDate(new Date(), "Europe/Budapest", "yyyy-MM-dd HH:mm");
  const cim = (teszt ? "🧪 Waze Budapest TESZT – " : "🚧 Waze Budapest – ") + riasztasok.length + " új esemény";
  const td = 'style="padding:8px;border-bottom:1px solid #eee"';
  const sorok = [], szoveg = [cim, ""];
  riasztasok.forEach(function (r) {
    const t = TIPUSOK[r.tipus] || ["📍", r.tipus, "#455a64"];
    const reszlet = ALTIPUSOK[r.altipus] || "";
    const tipus = reszlet && reszlet !== t[1] ? t[1] + " – " + reszlet : t[1];
    const hely = [r.utca, r.varos].filter(String).join(", ") || r.lat.toFixed(5) + ", " + r.lon.toFixed(5);
    const waze = "https://www.waze.com/ul?ll=" + r.lat + "%2C" + r.lon + "&navigate=no&zoom=17";
    const google = "https://www.google.com/maps/search/?api=1&query=" + r.lat + "%2C" + r.lon;
    const leiras = r.leiras ? '<div style="color:#666;font-size:12px">' + esc(r.leiras) + "</div>" : "";
    sorok.push("<tr><td " + td + '><span style="color:' + t[2] + ';font-weight:700;white-space:nowrap">' +
      t[0] + " " + esc(tipus) + "</span></td><td " + td + ">" + esc(hely) + leiras + "</td><td " + td + ">" +
      gomb(waze, "Waze", "#33ccff") + "</td><td " + td + ">" + gomb(google, "Google Maps", "#1a73e8") + "</td></tr>");
    szoveg.push("• " + tipus + " | " + hely, "  Waze: " + waze, "  Google Maps: " + google);
  });
  const html = '<div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#222">' +
    '<h2 style="margin:0 0 4px">' + esc(cim) + "</h2>" +
    '<div style="color:#666;margin-bottom:12px">' + most + "</div>" +
    '<table style="border-collapse:collapse;width:100%"><tr style="background:#f5f5f5;text-align:left">' +
    '<th style="padding:8px">Értesítés típusa</th><th style="padding:8px">Cím</th>' +
    '<th style="padding:8px">Waze</th><th style="padding:8px">Google Maps</th></tr>' +
    sorok.join("") + "</table></div>";
  MailApp.sendEmail({
    to: CIMZETT,
    subject: cim + " | " + Utilities.formatDate(new Date(), "Europe/Budapest", "HH:mm"),
    body: szoveg.join("\n"),
    htmlBody: html,
  });
}
