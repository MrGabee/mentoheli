"""
✉️ Olvasói hírek, levelek (olvasoi_hirek.json).

Minden tétel a „datum” napjától lehet esedékes; naponta egy megy ki,
ami nem fér bele, a következő napokra csúszik. Egy tétel:
  {"id": "egyedi-azonosito", "datum": "ÉÉÉÉ-HH-NN", "cim": "...",
   "szoveg": "...", "hashtagek": "#Csepel ..."}
A végére automatikusan kerül az elérhetőségek blokkja.
"""

import json
import os
from datetime import date

import allasok
from poszt_valtozatos import Stilus, kapcsolat_blokk

FAJL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "olvasoi_hirek.json")
OLVASOI_EMAIL = "olvaso@mrgabee.hu"
WHATSAPP_SZAM = "+36 70 754 0254"


def betolt():
    try:
        with open(FAJL, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def szoveg(nap, allapot):
    volt = allapot.setdefault("olvasoi_hir_volt", [])
    for t in betolt():
        if t["id"] in volt or date.fromisoformat(t["datum"]) > nap:
            continue
        volt.append(t["id"])
        st = Stilus("olvasoi_level", nap.isoformat())
        return "\n".join([
            t["cim"],
            st.vonal(),
            "",
            t["szoveg"].strip(),
            "",
            *kapcsolat_blokk(nap, t["id"], OLVASOI_EMAIL, WHATSAPP_SZAM, allasok.KAPCSOLAT_URL),
            "",
            t.get("hashtagek") or "#Csepel #olvasóihír",
        ])
    return ""
