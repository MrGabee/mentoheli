import re, requests
H = {"User-Agent": "facebookexternalhit/1.1"}
for u in ["https://www.police.hu/", "https://www.police.hu/hu/koral", "https://www.police.hu/hu/koral/eltunt-szemelyek",
          "https://www.police.hu/hu/koral/elfogatoparancs-alapjan-korozott-szemelyek", "https://www.police.hu/hu/koral/kozutijarmu-korozesek",
          "https://www.police.hu/hu/hirek-es-informaciok/legfrissebb-hireink/felhivasok",
          "https://www.police.hu/hu/koral/eltunt-szemelyek/1106241"]:
    try:
        r = requests.get(u, headers=H, timeout=20)
        print(u, r.status_code, re.findall(r'<meta (?:property|name)="(?:og:image|og:title|twitter:image)"[^>]*>', r.text)[:4])
    except Exception as e:
        print(u, e)
