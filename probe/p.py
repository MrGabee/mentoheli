import os, time, requests
u = os.environ["MAKE_WEBHOOK_URL"]
for adat in [{"kerdes": "nincs_ilyen_ag"}, {"kerdes": "utolso_poszt"}]:
    t = time.time()
    r = requests.post(u, json=adat, timeout=90)
    print(adat, "->", r.status_code, repr(r.text[:200]), f"{time.time()-t:.1f}s")
# v5 teszt
