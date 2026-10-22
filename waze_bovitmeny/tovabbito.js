// Az oldalról jövő georss válaszokat továbbadja a bővítmény hátterének, a
// háttér térképmozgató parancsait pedig az oldalnak.
window.addEventListener("message", (e) => {
  if (e.source !== window || !e.data || !e.data.wazeFigyelo) return;
  chrome.runtime.sendMessage({ tipus: "georss", status: e.data.status, adat: e.data.adat, url: e.data.url });
});

chrome.runtime.onMessage.addListener((uz, _kuldo, valasz) => {
  if (!uz || uz.tipus !== "parancs") return;
  const id = Math.random().toString(36).slice(2);
  const kesz = (e) => {
    if (e.source !== window || !e.data || !e.data.wazeParancsKesz || e.data.id !== id) return;
    window.removeEventListener("message", kesz);
    valasz({ ok: e.data.ok });
  };
  window.addEventListener("message", kesz);
  window.postMessage({ wazeParancs: { ...uz.parancs, id } }, "*");
  return true;
});

// A Waze-ablak méretét a háttér a csempék kiszámításához használja.
const meret = () => chrome.runtime.sendMessage({ tipus: "ablak", szel: window.innerWidth, mag: window.innerHeight });
window.addEventListener("load", meret);
window.addEventListener("resize", meret);
