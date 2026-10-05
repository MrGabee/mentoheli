"""
Egyszeri kísérlet: használhatók-e a ProxyScrape ingyenes proxyjai a Waze
élő térképhez, ha minden körben új proxyra váltunk.

1) Letölti a ProxyScrape ingyenes listáját.
2) Gyors előszűrés: melyik proxyn át tölt be egyáltalán a waze.com (HTTPS).
3) A leggyorsabb N proxyn egyenként: új böngésző, egy teljes lekérési kör
   (ugyanaz a kód, mint az éles monitorban), megszámolja a sikeres csempéket.
Semmit nem ment és nem küld e-mailt.
"""
import os
import time
from concurrent.futures import ThreadPoolExecutor

import requests

import waze_budapest_monitor as wm

LISTA_URL = ("https://api.proxyscrape.com/v4/free-proxy-list/get"
             "?request=display_proxies&proxy_format=protocolipport&format=text")
ELOSZURES_DB = int(os.environ.get("ELOSZURES_DB", "600"))
BONGESZO_DB = int(os.environ.get("BONGESZO_DB", "25"))


def lista_letoltes():
    sorok = requests.get(LISTA_URL, timeout=30).text.split()
    proxyk = [s.strip() for s in sorok
              if s.startswith(("http://", "socks4://", "socks5://"))]
    print(f"📋 ProxyScrape lista: {len(proxyk)} proxy")
    return proxyk


def gyors_proba(proxy):
    # A requests a socks5h sémával a proxyra bízza a névfeloldást.
    p = proxy.replace("socks5://", "socks5h://").replace("socks4://", "socks4a://")
    kezdet = time.monotonic()
    try:
        r = requests.get("https://www.waze.com/live-map", timeout=10,
                         proxies={"http": p, "https": p})
        if r.status_code == 200 and "waze" in r.text.lower():
            return proxy, time.monotonic() - kezdet
    except Exception:
        pass
    return proxy, None


def bongeszo_proba(proxy):
    wm.PROXY_SZERVER = proxy
    m = wm.WazeMunkamenet()
    kezdet = time.monotonic()
    eredmeny = {"proxy": proxy, "csempe": 0, "riasztas": 0, "statuszok": [], "hiba": ""}
    try:
        m.indit()
        valaszok, _ = m.kor()
        eredmeny["csempe"] = len(valaszok)
        eredmeny["riasztas"] = sum(len(v.get("alerts", [])) for v in valaszok.values())
        eredmeny["statuszok"] = m.statuszok[-8:]
    except Exception as e:
        eredmeny["hiba"] = f"{type(e).__name__}: {str(e).splitlines()[0][:80]}"
    finally:
        m.bezar()
    eredmeny["mp"] = round(time.monotonic() - kezdet)
    return eredmeny


def main():
    proxyk = lista_letoltes()[:ELOSZURES_DB]
    with ThreadPoolExecutor(max_workers=100) as ex:
        elo = [(p, t) for p, t in ex.map(gyors_proba, proxyk) if t is not None]
    elo.sort(key=lambda x: x[1])
    print(f"🔎 Előszűrés: {len(elo)}/{len(proxyk)} proxyn át tölt be a waze.com")

    eredmenyek = []
    for p, t in elo[:BONGESZO_DB]:
        e = bongeszo_proba(p)
        e["elo_mp"] = round(t, 1)
        eredmenyek.append(e)
        print(f"  {p:<32} előszűrés {t:4.1f} mp | csempe {e['csempe']}/8 | "
              f"riasztás {e['riasztas']} | státusz {e['statuszok']} | {e['mp']} mp {e['hiba']}")

    jo = [e for e in eredmenyek if e["csempe"] > 0]
    teljes = [e for e in eredmenyek if e["csempe"] == 8]
    osszegzes = (f"Lista: {len(proxyk)} | betölt: {len(elo)} | böngészővel próbálva: "
                 f"{len(eredmenyek)} | adatot hozott: {len(jo)} | mind a 8 csempe: {len(teljes)}")
    print("📊 " + osszegzes)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(f"### Ingyenes proxy teszt\n\n{osszegzes}\n\n"
                    "| proxy | előszűrés mp | csempe | riasztás | státuszok | idő mp | hiba |\n"
                    "|---|---|---|---|---|---|---|\n")
            for e in eredmenyek:
                f.write(f"| {e['proxy']} | {e['elo_mp']} | {e['csempe']}/8 | {e['riasztas']} | "
                        f"{e['statuszok']} | {e['mp']} | {e['hiba']} |\n")


if __name__ == "__main__":
    main()
