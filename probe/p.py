import sys; sys.path.insert(0,".")
from datetime import date, timedelta, datetime
from zoneinfo import ZoneInfo
import kerulet_forrasok as kf, kerulet_programok as kp, ezen_a_napon as ez, csepeli_erdekesseg as ce, kerdes_nektek as kn, esti_idojaras as ei
ma=datetime.now(ZoneInfo("Europe/Budapest")).date()+timedelta(days=1)
pentek=ma+timedelta(days=(4-ma.weekday())%7)
for nev,f in [("PROGRAMOK",lambda:kp.reggeli_szoveg(ma)),("HETVEGE",lambda:kp.hetvegi_szoveg(pentek)),("EZEN",lambda:ez.szoveg(ma)),("ERDEKESSEG",lambda:ce.szoveg(ma,[])),("KERDES",lambda:kn.szoveg(ma)),("ESTI",lambda:ei.szoveg(ma))]:
    print("#"*20,nev); 
    try: print(repr(f()) if not f() else f())
    except Exception as e: import traceback; traceback.print_exc()
print(len(ce.jeloltek()), ce.jeloltek()[:60])
