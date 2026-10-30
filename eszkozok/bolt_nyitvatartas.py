"""Ideiglenes felderítő: a láncok boltkeresőit böngészővel betölti, és a
csepeli (1211–1215) és szigetszentmiklósi boltok körüli szöveget kiírja. Nem posztol."""
import os
import re
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
MINTA = re.compile(os.environ.get("MINTA", r"Csepel|121[1-5]|Szigetszentmikl"), re.I)


def kornyek(szoveg, n=700):
    ki, utolso = [], -10**9
    for m in MINTA.finditer(szoveg):
        if m.start() - utolso < n:
            continue
        utolso = m.start()
        ki.append(szoveg[max(0, m.start() - 150):m.start() + n].replace("\n", " "))
    return ki[:12]


with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    for url in os.environ["URLEK"].split():
        print(f"\n\n======== {url}")
        page = b.new_context(user_agent=UA, locale="hu-HU", viewport={"width": 1400, "height": 1000}).new_page()
        valaszok = []
        page.on("response", lambda r: valaszok.append(r) if r.request.resource_type in ("xhr", "fetch", "document") else None)
        try:
            page.goto(url, wait_until="load", timeout=45000)
            page.wait_for_timeout(8000)
        except Exception as e:
            print("  betöltési hiba:", e)
        for r in valaszok:
            try:
                t = r.text()
            except Exception:
                continue
            talalat = kornyek(t)
            if talalat:
                print(f"\n--- {r.status} {r.url[:160]}")
                for s in talalat:
                    print("  •", s)
        try:
            body = page.inner_text("body")
            print("\n--- OLDALSZÖVEG találatai")
            for s in kornyek(body):
                print("  •", s)
        except Exception as e:
            print("  oldalszöveg hiba:", e)
        page.context.close()
    b.close()
