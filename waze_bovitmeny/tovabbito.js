// Az oldalról jövő georss válaszokat továbbadja a bővítmény hátterének.
window.addEventListener("message", (e) => {
  if (e.source !== window || !e.data || !e.data.wazeFigyelo) return;
  chrome.runtime.sendMessage({ tipus: "georss", status: e.data.status, adat: e.data.adat });
});

// A Waze-ablak méretét a háttér a csempék kiszámításához használja.
const meret = () => chrome.runtime.sendMessage({ tipus: "ablak", szel: window.innerWidth, mag: window.innerHeight });
window.addEventListener("load", meret);
window.addEventListener("resize", meret);
