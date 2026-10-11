import subprocess, sys
subprocess.run("git fetch -q --depth=1 origin claude/project-thread-oeicnh && git checkout FETCH_HEAD -- veradas.py poszt_valtozatos.py", shell=True, check=True)
sys.path.insert(0, ".")
from datetime import date
import veradas
l = veradas.esemenyek()
for e in l:
    print(" ", e)
for h in [date(2026, 10, 12), date(2026, 10, 19)]:
    print("=" * 40, h)
    print(veradas.heti_szoveg(h, l))
