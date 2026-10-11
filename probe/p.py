import requests
for u in ["https://mrgabee.github.io/mentoheli/szamlak/szamlak.html",
          "https://mrgabee.github.io/mentoheli/kepek/rendorseg_korozes.png",
          "https://mrgabee.github.io/mentoheli/index.html"]:
    r = requests.get(u, timeout=30)
    print(u, r.status_code, r.headers.get("content-type"), len(r.content))
