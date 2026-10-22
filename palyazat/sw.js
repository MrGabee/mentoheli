// Telepíthető alkalmazás: a keret gyorsítótárból jön, az adat mindig frissen,
// hálózat nélkül pedig a legutóbb letöltött (titkosított) adat látszik.
const TAR = "palyazat-v1";
const KERET = ["./", "index.html", "manifest.webmanifest", "ikon-192.png", "ikon-512.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(TAR).then((c) => c.addAll(KERET)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys()
    .then((k) => Promise.all(k.filter((n) => n !== TAR).map((n) => caches.delete(n))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  // hálózat elöl, hiba esetén a tárolt példány
  e.respondWith(
    fetch(e.request, { cache: "no-store" })
      .then((v) => {
        if (v.ok) { const m = v.clone(); caches.open(TAR).then((c) => c.put(e.request.url.split("?")[0], m)); }
        return v;
      })
      .catch(() => caches.match(e.request.url.split("?")[0]).then((t) => t || caches.match("index.html")))
  );
});
