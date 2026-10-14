import subprocess, sys
subprocess.run(["git","fetch","-q","--depth=1","origin","main"],check=True)
subprocess.run(["git","checkout","-q","FETCH_HEAD","--","allasok.py"],check=True)
sys.path.insert(0,".")
import allasok
r=allasok.varosgazda()
print("VAROSGAZDA:", None if r is None else len(r))
for x in (r or [])[:30]: print(x)
