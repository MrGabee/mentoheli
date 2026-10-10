// Számla Figyelő - service worker (telepíthető app).
// Szándékosan "hálózat először": az oldal mindig a legfrissebb verzió,
// a gyorsítótár csak akkor kell, ha nincs net (offline vázlat). Az API-
// hívások (más domain) és minden nem-GET kérés érintetlenül megy át.
const CACHE = "szamla-figyelo-v2";
const ALAP = ["./szamlak.html", "./manifest.webmanifest", "./ikonok/ikon-192.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ALAP)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((kulcsok) => Promise.all(kulcsok.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET" || new URL(req.url).origin !== self.location.origin) return;
  e.respondWith(
    fetch(req)
      .then((valasz) => {
        if (valasz.ok) {
          const masolat = valasz.clone();
          caches.open(CACHE).then((c) => c.put(req, masolat));
        }
        return valasz;
      })
      .catch(() => caches.match(req, { ignoreSearch: true }).then((m) => m || caches.match("./szamlak.html")))
  );
});
