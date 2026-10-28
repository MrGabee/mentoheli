# Ideiglenes: az utolsó MÁV/Volán eseményt kiküldi az új arculattal (minta).
import mav_monitor as m

for e in m.lekerdez_lista():
    tipus = m.esemeny_tipus(e["url"], e["cim"], e.get("reszlet", ""))
    if tipus is None:
        continue
    e["tipus"] = tipus
    datum, reszlet = m.lekerdez_cikk_datuma(e["url"])
    e["datum"] = datum or "—"
    e["reszlet"] = reszlet
    print(f"Minta: {tipus} | {e['cim'][:90]} | {e['datum']}")
    m.email_kuldes([e])
    break
else:
    print("Nem találtam eseményt.")
