const mezok = ["scriptUrl", "titok"];

async function frissit() {
  const t = await chrome.storage.local.get(["allapot", "levelAllapot", "kuldendo", "latott"]);
  document.getElementById("allapot").textContent = [
    t.allapot || "Még nem jött adat. Nyiss meg egy Waze Live Map fület Budapest fölött.",
    t.levelAllapot || "",
    `Megjegyzett riasztások: ${Object.keys(t.latott || {}).length}`,
    t.kuldendo && t.kuldendo.length ? `Elküldésre vár: ${t.kuldendo.length}` : "",
  ].filter(Boolean).join("\n");
}

(async () => {
  const t = await chrome.storage.local.get(mezok);
  for (const m of mezok) document.getElementById(m).value = t[m] || "";
  frissit();
  setInterval(frissit, 2000);
})();

document.getElementById("mentes").onclick = async () => {
  const uj = {};
  for (const m of mezok) uj[m] = document.getElementById(m).value.trim();
  await chrome.storage.local.set(uj);
  document.getElementById("mentes").textContent = "Mentve ✓";
};

document.getElementById("teszt").onclick = () => {
  chrome.runtime.sendMessage({ tipus: "teszt" });
  document.getElementById("teszt").textContent = "Küldve…";
};
