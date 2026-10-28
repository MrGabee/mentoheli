"""Ideiglenes: minta mentőhelikopteres levél valódi térképpel és helynevekkel (nem küld e-mailt)."""
import base64, email, os, smtplib, sys, time
sys.path.insert(0, ".")
os.environ.setdefault("EMAIL_KULDO", "minta@pelda.hu")
os.environ.setdefault("EMAIL_JELSZO", "x")
os.environ.setdefault("EMAIL_CIMZETT", "minta@pelda.hu")
import monitor as m
import heli_pozicio as hp

kuldott = []
class Al:
    def __init__(s, *a): pass
    def __enter__(s): return s
    def __exit__(s, *a): pass
    def login(s, *a): pass
    def sendmail(s, f, t, msg): kuldott.append(msg)
smtplib.SMTP_SSL = Al

most = int(time.time())
# Kitalált útvonal: Budaörs → Szent Imre kórház környéke
pontok = [[most - 1100, 47.4507, 18.9617, 0, 0], [most - 1000, 47.4540, 18.9800, 250, 200],
          [most - 900, 47.4580, 19.0000, 320, 230], [most - 800, 47.4610, 19.0150, 200, 160],
          [most - 720, 47.4627, 19.0255, 40, 50]]
nyom = {"ha-hbg": {"pontok": pontok}}
for tipus in ("FELSZALLAS", "LESZALLAS"):
    m.email_kuldes({"tipus": tipus, "kulcs": "reg:ha-hbg", "adat": {
        "callsign": "MEDIC3", "datum": "28 Oct 2026", "atd": "19:21",
        "landed": None if tipus == "FELSZALLAS" else "19:52", "elo": tipus == "FELSZALLAS",
        "flight_id": "3c9f1a2b"}}, {"ha-hbg": {"pontok": pontok[:2] if tipus == "FELSZALLAS" else pontok}})
for i, raw in enumerate(kuldott):
    for part in email.message_from_string(raw).walk():
        if part.get_content_type() in ("text/html", "image/png"):
            print(f"=====MINTA{i}:{part.get_content_type()}=====")
            print(base64.b64encode(part.get_payload(decode=True)).decode())
            print("=====VEGE=====")
