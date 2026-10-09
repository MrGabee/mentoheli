// A Waze-oldalon fut, és csak elolvassa a térkép saját georss válaszait.
// Saját kérést nem küld.
(() => {
  const GEORSS = "/live-map/api/georss";
  const kuld = (status, adat) => window.postMessage({ wazeFigyelo: true, status, adat }, "*");

  const eredetiFetch = window.fetch;
  window.fetch = async function (...args) {
    const valasz = await eredetiFetch.apply(this, args);
    try {
      const url = typeof args[0] === "string" ? args[0] : args[0]?.url || "";
      if (url.includes(GEORSS)) {
        if (valasz.ok) valasz.clone().json().then((d) => kuld(valasz.status, d)).catch(() => {});
        else kuld(valasz.status, null);
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
        kuld(this.status, adat);
      });
    }
    return eredetiOpen.call(this, metodus, url, ...tobbi);
  };
})();
