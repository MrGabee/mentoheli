import sys, functools
print = functools.partial(print, flush=True)
sys.path.insert(0, "probe")
from datetime import date
import allasok, hivatali_hirek, kerulet_forrasok as kf, kerulet_programok as kp
ma = date.today()
print("### ALLAS\n" + str(allasok.heti_szoveg(date(2026, 10, 14), {})))
print("### HIVATALI\n" + str(hivatali_hirek.szoveg(ma, {"hivatali_latott": []})))
l = kf.kultik()
print("### KULTIK napok", sorted({f["nap"] for f in l or []}), l[:3] if l else l)
print("### REGGELI\n" + str(kp.reggeli_szoveg(ma, [])))
