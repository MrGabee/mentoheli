import re, requests
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
     "Accept-Language": "hu-HU,hu;q=0.9", "Accept": "text/html,application/xhtml+xml"}
URLS = ["https://allas.csepel.hu/", "https://varosgazda.eu/",
        "https://www.profession.hu/allasok/budapest/1,0,23,csepel",
        "https://hu.indeed.com/jobs?q=&l=budapest+xxi.+ker%C3%BClet",
        "https://allas.jofogas.hu/budapest/xxi-kerulet/allasajanlat"]
for u in URLS:
    print("=" * 30, u)
    try:
        r = requests.get(u, headers=H, timeout=30)
    except Exception as e:
        print("HIBA", e); continue
    t = r.text
    print("STATUS", r.status_code, len(t), r.url)
    print("TITLE", re.findall(r"<title>(.*?)</title>", t, re.S)[:1])
    print("LD+JSON", len(re.findall(r'application/ld\+json', t)), "JobPosting", t.count("JobPosting"), "__NEXT_DATA__", t.count("__NEXT_DATA__"))
    links = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', t, re.S)
    seen = 0
    for h, txt in links:
        txt = " ".join(re.sub(r"<[^>]+>", " ", txt).split())
        if len(txt) > 15 and any(k in h.lower() for k in ["allas", "job", "karrier", "hirdet", "munka", "pozic", "viewjob", "/rc/"]):
            print("  L", h[:150], "|", txt[:90]); seen += 1
            if seen >= 15: break
    if "varosgazda" in u:
        for h, txt in links:
            if re.search(r"karrier|állás|allas|munka", h + txt, re.I):
                print("  V", h, "|", " ".join(re.sub(r"<[^>]+>", " ", txt).split())[:80])
