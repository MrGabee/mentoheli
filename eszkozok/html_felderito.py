"""Ideiglenes felderítő: weboldalak szerkezetét nézi meg (új sportági
adatforrásokhoz). Csak kiír, nem posztol."""
import os
import re
import html
import requests

H = {"User-Agent": os.environ.get("UA") or "Mozilla/5.0 (X11; Linux x86_64) Chrome/129.0 Safari/537.36"}
MINTA = re.compile(os.environ.get("MINTA") or "Csepel", re.I)

for url in os.environ.get("URLEK", "").split():
    try:
        r = requests.get(url, headers=H, timeout=30)
    except Exception as ex:
        print(f"\n### {url} -> HIBA {ex}")
        continue
    t = r.text
    print(f"\n### {url} -> {r.status_code} {len(t)} bájt")
    linkek = sorted(set(re.findall(r'href="([^"]+)"', t)))
    print(f"  {len(linkek)} link; a mintára illők:")
    for l in [l for l in linkek if MINTA.search(l)][:40]:
        print("   L", html.unescape(l))
    for i, m in enumerate(MINTA.finditer(t)):
        if i >= 6:
            break
        print(f"  --- találat {i + 1} ---")
        print("  " + t[max(0, m.start() - 1200):m.end() + 1500].replace("\n", "\n  "))
    print("  --- szöveg ---")
    print("  " + re.sub(r"\s+", " ", html.unescape(re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", t, flags=re.S)))[:3000])
