import re, requests
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124", "Accept-Language": "hu",
     "X-Requested-With": "XMLHttpRequest", "Referer": "https://www.ovsz.hu/hu/ver/veradasok"}
u = "https://www.ovsz.hu/sites/all/scripts/gps2020/esemenyek-table.php"
r = requests.post(u, headers=H, timeout=40, data={"latitude_percent": 1.0 - 0.5835, "longitude_percent": 0.4457,
                                                   "kereses_radius": 10, "idopontfoglalas": "off"})
print("STATUS", r.status_code, len(r.text))
print(r.text[:9000])
