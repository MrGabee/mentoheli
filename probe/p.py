import sys; sys.path.insert(0,"probe")
from datetime import date
import allasok
a={}
t=allasok.heti_szoveg(date(2026,10,15),a)
print("=====POSZT=====");print(t);print("látott:",len(a["allas_latott"]))
