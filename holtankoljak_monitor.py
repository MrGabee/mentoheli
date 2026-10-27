"""
⛽ Holtankoljak.hu üzemanyagár-változás figyelő
Adatforrás: a holtankoljak.hu kezdőlapjának „Üzemanyagár-változás” kártyája
(naponta frissül, dátummal). Csak akkor posztol, ha a szöveg árváltozásról szól
(emelkedés / csökkenés), a „nem változtak” napokat kihagyja.
A Holtankoljak.hu Facebook-oldalával közös napi zárat használ, hogy ugyanarról
a változásról ne menjen ki két poszt egy nap.
"""
import html
import re
import requests

import fb_oldal_figyelo as fb

URL = "https://holtankoljak.hu/"
ALLAPOT_FAJL = "holtankoljak_allapot.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/129.0 Safari/537.36"}
VALTOZAS = re.compile(r"emelked|emeli|emelés|csökken|csökkent|drágul|olcsóbb|Ft-tal|forinttal", re.I)


def _szoveg(resz):
    resz = re.sub(r"</p>|<br\s*/?>", "\n", resz)
    resz = html.unescape(re.sub(r"<[^>]+>", "", resz))
    return [s.strip() for s in resz.split("\n") if s.strip()]


def kartya(t):
    """(dátum, bekezdések) az „Üzemanyagár-változás” kártyából, vagy None."""
    m = re.search(r"Üzemanyagár-változás.*?card-subtitle[^>]*>\s*([\d-]{10})\s*<.*?card-text\">(.*?)</div>", t, re.S)
    if not m:
        return None
    return m.group(1), _szoveg(m.group(2))


TULAJDONNEV = ("Magyar", "MOL", "Mol", "Budapest", "OMV", "Shell", "Holtankoljak")


def poszt_szoveg(bekezdesek):
    elso, *tobbi = bekezdesek
    if len(elso) > 1 and elso[1].islower() and not elso.startswith(TULAJDONNEV):
        elso = elso[0].lower() + elso[1:]
    sorok = ["⛽ ÜZEMANYAGÁR-VÁLTOZÁS", "", f"A Holtankoljak.hu tájékoztatása szerint {elso}"]
    for b in tobbi:
        if b.startswith("A Holtankoljak.hu aktuális áradatai alapján"):
            sorok += ["", "Az országos átlagárak most:"]
        else:
            sorok.append(b)
    sorok += ["", f"👉 {URL}", "", "#üzemanyagár #benzin #gázolaj #Csepel"]
    return "\n".join(sorok)


def main():
    print(f"⛽ Holtankoljak.hu figyelő – {fb.magyar_ido().strftime('%Y.%m.%d %H:%M:%S')}")
    try:
        r = requests.get(URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
    except Exception as ex:
        print(f"  ⚠️ Nem érhető el: {ex}")
        return
    k = kartya(r.text)
    if not k:
        print("  ⚠️ Nem találom az árváltozás-kártyát (változott az oldal?).")
        return
    datum, bekezdesek = k
    allapot = fb.betolt(ALLAPOT_FAJL, {})
    if allapot.get("utolso_datum") == datum:
        print(f"  ✔️ A {datum} napi kártyát már láttam.")
        return
    szoveg = "\n".join(bekezdesek)
    print(f"  🆕 {datum}: {szoveg[:200]}")
    if not VALTOZAS.search(szoveg):
        print("  ⏭️ Nincs árváltozás, nem posztolok.")
    elif fb.napi_zar_volt(ALLAPOT_FAJL):
        print("  ⏭️ Ma már ment üzemanyagár-poszt (FB-oldalról).")
    else:
        poszt = poszt_szoveg(bekezdesek)
        print("\n" + poszt + "\n")
        if fb.FACEBOOK_POSZTOLAS_AKTIV:
            if not fb.facebook_poszt_kuldese(poszt):
                return  # a következő futás újrapróbálja
            fb.napi_zar_beallit(ALLAPOT_FAJL)
            fb.csendes_ablak(40)
    allapot = fb.betolt(ALLAPOT_FAJL, {})
    allapot["utolso_datum"] = datum
    with open(ALLAPOT_FAJL, "w", encoding="utf-8") as f:
        fb.json.dump(allapot, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
