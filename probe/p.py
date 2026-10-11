import os, requests
url = os.environ.get("MAKE_WEBHOOK_URL_SZINES", "")
print("szines titok beallitva:", bool(url), "uj fiok:", url.endswith("4i62y6"))
if url:
    r = requests.post(url, json={"message": "🧪 Próbaposzt: az új posztolási csatornámat tesztelem. Hamarosan törlöm, bocsi a zavarásért! 🙂", "link": ""}, timeout=30)
    print("valasz:", r.status_code, r.text[:100])
