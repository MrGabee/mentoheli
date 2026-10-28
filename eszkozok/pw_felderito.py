"""Ideiglenes felderítő: Playwrighttal betölt egy oldalt, kiírja a háttérben
hívott API-kat (XHR/fetch) és az oldal szövegét. Nem posztol."""
import os
from playwright.sync_api import sync_playwright

URL = os.environ["URL"]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_context(user_agent=UA, viewport={"width": 1400, "height": 1000}).new_page()
    valaszok = []
    page.on("response", lambda r: valaszok.append(r) if r.request.resource_type in ("xhr", "fetch") else None)
    page.goto(URL, wait_until="load", timeout=45000)
    page.wait_for_timeout(6000)
    for r in valaszok:
        print(f"\n### {r.status} {r.request.method} {r.url}")
        try:
            print(r.text()[:2500])
        except Exception as ex:
            print("  (nem olvasható)", ex)
    print("\n### OLDAL SZÖVEGE\n" + page.inner_text("body")[:6000])
    for u in os.environ.get("FETCH", "").split():
        res = page.evaluate("""async (u) => { try { const r = await fetch(u);
            return {s: r.status, t: (await r.text()).slice(0, 4000)}; } catch (e) { return {s: -1, t: String(e)}; } }""", u)
        print(f"\n### FETCH {u} -> {res['s']}\n{res['t']}")
    b.close()
