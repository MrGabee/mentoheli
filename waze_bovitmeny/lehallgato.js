// A Waze-oldalon fut: elolvassa a térkép saját georss válaszait, és a háttér
// kérésére egérhúzással (vagy dupla kattintással) mozgatja a térképet, hogy ne
// kelljen újratölteni az oldalt. Saját kérést nem küld.
(() => {
  const GEORSS = "/live-map/api/georss";
  const kuld = (status, adat, url) => window.postMessage({ wazeFigyelo: true, status, adat, url }, "*");

  const eredetiFetch = window.fetch;
  window.fetch = async function (...args) {
    const valasz = await eredetiFetch.apply(this, args);
    try {
      const url = typeof args[0] === "string" ? args[0] : args[0]?.url || String(args[0] || "");
      if (url.includes(GEORSS)) {
        if (valasz.ok) valasz.clone().json().then((d) => kuld(valasz.status, d, url)).catch(() => {});
        else kuld(valasz.status, null, url);
      }
    } catch (e) {}
    return valasz;
  };

  const eredetiOpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (metodus, url, ...tobbi) {
    if (String(url).includes(GEORSS)) {
      this.addEventListener("load", () => {
        let adat = null;
        try { adat = this.status === 200 ? JSON.parse(this.responseText) : null; } catch (e) {}
        kuld(this.status, adat, String(url));
      });
    }
    return eredetiOpen.call(this, metodus, url, ...tobbi);
  };

  // Háttérbe tett fülön a böngésző nem rajzol, és a térkép a húzás végén a
  // régi helyet töltené le; ilyenkor a rajzolási lépés időzítővel fut le.
  const eredetiRaf = window.requestAnimationFrame.bind(window);
  const eredetiCaf = window.cancelAnimationFrame.bind(window);
  const idozitok = new Set();
  window.requestAnimationFrame = (cb) => {
    if (!document.hidden) return eredetiRaf(cb);
    const id = setTimeout(() => { idozitok.delete(id); cb(performance.now()); }, 0);
    idozitok.add(id);
    return id;
  };
  window.cancelAnimationFrame = (id) => (idozitok.delete(id) ? clearTimeout(id) : eredetiCaf(id));

  const varj = (ms) => new Promise((r) => setTimeout(r, ms));
  const terkep = () => document.querySelector(".leaflet-container") ||
    document.elementFromPoint(innerWidth / 2, innerHeight / 2);

  function eger(cel, tipus, x, y, extra = {}) {
    const k = { bubbles: true, cancelable: true, view: window, clientX: x, clientY: y,
      button: 0, buttons: tipus === "up" ? 0 : 1, ...extra };
    cel.dispatchEvent(new PointerEvent("pointer" + tipus, { ...k, pointerId: 1, pointerType: "mouse", isPrimary: true }));
    cel.dispatchEvent(new MouseEvent("mouse" + tipus, k));
  }

  // dx, dy képpontnyi húzás a térkép közepéről; utána szünet, hogy ne guruljon tovább.
  async function huz(dx, dy) {
    const t = terkep();
    if (!t) return false;
    const r = t.getBoundingClientRect();
    const x0 = r.left + r.width / 2, y0 = r.top + r.height / 2;
    eger(t, "down", x0, y0);
    const lepes = 6;
    for (let i = 1; i <= lepes; i++) {
      await varj(30);
      eger(t, "move", x0 + dx * i / lepes, y0 + dy * i / lepes);
    }
    await varj(200);
    eger(t, "up", x0 + dx, y0 + dy);
    return true;
  }

  // Dupla kattintás a közepére: egy szinttel nagyít, Shifttel kicsinyít.
  function nagyit(ki) {
    const t = terkep();
    if (!t) return false;
    const r = t.getBoundingClientRect();
    const k = { bubbles: true, cancelable: true, view: window, clientX: r.left + r.width / 2,
      clientY: r.top + r.height / 2, button: 0, detail: 2, shiftKey: ki };
    t.dispatchEvent(new MouseEvent("dblclick", k));
    return true;
  }

  window.addEventListener("message", async (e) => {
    const p = e.source === window && e.data && e.data.wazeParancs;
    if (!p) return;
    const ok = p.tipus === "huz" ? await huz(p.dx, p.dy) : p.tipus === "nagyit" ? nagyit(p.ki) : false;
    window.postMessage({ wazeParancsKesz: true, id: p.id, ok }, "*");
  });
})();
