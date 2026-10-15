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
        return "\n".join([
            t["cim"],
            "••••••••••••••••••••••••",
            "",
            t["szoveg"].strip(),
            "",
            "Ha neked is van problémád a környéken, vagy bármilyen hírt, infót tudsz, írj nekem, és utánajárok:",
            "💬 Facebook-üzenetben (az oldal tetején az „Üzenetküldés” gombbal)",
            f"📱 WhatsApp-üzenetben: {WHATSAPP_SZAM}",
            f"📩 e-mailben: {OLVASOI_EMAIL}",
            "",
            t.get("hashtagek") or "#Csepel #olvasóihír",
        ])
    return ""
