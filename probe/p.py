import requests
H={"User-Agent":"Mozilla/5.0 (compatible; MrGabeeHirek/1.0)"}
for u in ["https://tiesz.hu/feed/","https://tiesz.hu/wp-json/wp/v2/posts?per_page=3","https://tiesz.hu/robots.txt","https://tiesz.hu/sitemap.xml"]:
    try:
        r=requests.get(u,headers=H,timeout=30)
        print("=====",u,r.status_code,r.headers.get("content-type"),len(r.text))
        print(r.text[:1500])
    except Exception as e: print(u,e)
