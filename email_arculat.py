"""
📧 Közös e-mail arculat a figyelők leveleihez (BKK zavar, kijelző, közút).

Ugyanaz a kártyás rendszer, mint az Útinform Figyelő leveleinél:
felül színes csík (piros = baleset, sárga = terelés/késés/egyéb,
zöld = lezárult), alatta jelvény + címke + cím, majd a törzs és gombok.

Gmail a <style> blokkot eldobja, ezért minden stílus inline.
"""

import html as _html

SZIN = {
    "piros": "#dc2626",
    "sarga": "#d97706",
    "sarga_szoveg": "#b45309",
    "zold": "#16a34a",
    "kek": "#1f5fae",
}

# BKK járatszín-jelvények: busz kék, villamos sárga, troli piros, HÉV zöld, éjszakai fekete
JARAT_SZIN = {
    "busz": ("#009ee3", "#ffffff"),
    "villamos": ("#ffd800", "#1b232c"),
    "troli": ("#e41f18", "#ffffff"),
    "hev": ("#00a77e", "#ffffff"),
    "ejszakai": ("#1b232c", "#ffffff"),
}


def esc(s):
    return _html.escape(str(s if s is not None else ""), quote=True)


def jarat_fajta(vonal, eszkoz_tipus=None):
    """Eldönti a jelvény színét a vonalszámból (és ha van, a jármű típusából)."""
    t = (eszkoz_tipus or "").upper()
    v = str(vonal or "").upper()
    if t == "TRAM":
        return "villamos"
    if t == "TROLLEYBUS":
        return "troli"
    if t in ("RAIL", "SUBURBAN_RAILWAY") or v.startswith("H"):
        return "hev"
    if v[:1] == "9" and len(v.rstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ")) == 3:
        return "ejszakai"
    if t == "BUS":
        return "busz"
    # Típus nélkül: a csepeli/budapesti villamosok és trolik számai
    szam = v.rstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    if szam.isdigit():
        n = int(szam)
        if n in (2, 4, 6, 12, 14, 17, 19, 24, 28, 37, 41, 42, 47, 48, 49, 50, 51, 52, 56, 59, 60, 61, 62, 69):
            return "villamos"
        if 70 <= n <= 83:
            return "troli"
    return "busz"


def jarat_jelveny(vonal, eszkoz_tipus=None):
    hatter, betu = JARAT_SZIN[jarat_fajta(vonal, eszkoz_tipus)]
    return (f'<span style="display:inline-block;min-width:34px;text-align:center;font-weight:bold;'
            f'font-size:16px;line-height:1;padding:6px 8px;border-radius:4px;margin:0 6px 4px 0;'
            f'background:{hatter};color:{betu};font-family:Arial,sans-serif">{esc(vonal)}</span>')


def gomb(szoveg, url, masodlagos=False):
    if not url:
        return ""
    stilus = (f"background:#ffffff;color:{SZIN['kek']};border:1px solid #c9d6e6;" if masodlagos
              else f"background:{SZIN['kek']};color:#ffffff;border:1px solid {SZIN['kek']};")
    return (f'<a href="{esc(url)}" style="display:inline-block;{stilus}text-decoration:none;font-weight:bold;'
            f'padding:10px 16px;border-radius:6px;font-size:14px;margin:6px 8px 6px 0">{szoveg}</a>')


def adat_tabla(sorok):
    """sorok: [(címke, érték), ...] – az üres értékű sorok kimaradnak."""
    tr = "".join(
        f'<tr><td style="padding:7px 12px 7px 0;border-top:1px solid #eef1f4;color:#6b7682;width:120px;vertical-align:top">{esc(c)}</td>'
        f'<td style="padding:7px 0;border-top:1px solid #eef1f4;vertical-align:top">{esc(e)}</td></tr>'
        for c, e in sorok if e)
    if not tr:
        return ""
    return ('<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="border-collapse:collapse;font-size:14px;margin:10px 0 6px">{tr}</table>')


def led(szoveg, felirat="A jármű kijelzőjén"):
    """A kijelző szövege úgy, mint a buszon: borostyán betű fekete alapon."""
    return ('<div style="background:#111111;border-radius:6px;padding:14px 16px;margin:10px 0;'
            'font-family:\'Courier New\',monospace;font-weight:bold;font-size:18px;letter-spacing:2px;'
            'color:#ffb000;text-transform:uppercase">'
            f'<div style="font-size:11px;letter-spacing:1px;color:#8a6a1e;margin-bottom:4px">{esc(felirat)}</div>'
            f'{esc(szoveg)}</div>')


def bekezdes(szoveg):
    return f'<p style="margin:8px 0">{esc(szoveg)}</p>' if szoveg else ""


def kartya(szin, cimke, cim, test, jelvenyek="", cimke_szin=None, lab=""):
    """Egy esemény-kártya. A `test` és a `jelvenyek` már kész HTML."""
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="background:#ffffff;border:1px solid #dfe4ea;border-radius:8px;border-collapse:separate;margin:0 0 16px">'
        f'<tr><td style="height:6px;line-height:6px;font-size:0;background:{szin};border-radius:8px 8px 0 0">&nbsp;</td></tr>'
        '<tr><td style="padding:18px 22px 6px">'
        + (f'<div style="margin-bottom:6px">{jelvenyek}</div>' if jelvenyek else "")
        + f'<div style="font-size:12px;letter-spacing:1.2px;text-transform:uppercase;font-weight:bold;color:{cimke_szin or szin}">{esc(cimke)}</div>'
        f'<div style="font-size:19px;font-weight:bold;line-height:1.3;color:#1b232c;margin-top:2px">{esc(cim)}</div>'
        '</td></tr>'
        f'<tr><td style="padding:4px 22px 14px;font-size:15px;line-height:1.5;color:#1b232c">{test}</td></tr>'
        + (f'<tr><td style="padding:12px 22px 16px;border-top:1px solid #eef1f4;color:#8a949e;font-size:12px">{lab}</td></tr>' if lab else "")
        + '</table>')


def keret(tartalom, lablec="automatikus értesítés"):
    return ('<!DOCTYPE html><html lang="hu"><head><meta charset="UTF-8"></head>'
            '<body style="margin:0;padding:0;background:#f3f5f7">'
            '<div style="background:#f3f5f7;padding:20px 10px;font-family:Arial,Helvetica,sans-serif;color:#1b232c">'
            f'<div style="max-width:600px;margin:0 auto">{tartalom}'
            f'<div style="text-align:center;color:#9aa4ae;font-size:11px;padding:4px 0 0">{esc(lablec)}</div>'
            '</div></div></body></html>')
