import asyncio, base64, hashlib, json, os, re
from playwright.async_api import async_playwright
OUT = 'windy/szonda3'
REGI = {
 '71b7e7e9aca2711b69': 'worldcam:553', '6f9b8ae4ed55d74007': 'worldcam:30818', '766785dcad6cb97d5a': None,
 '8a2c8ae42599798567': 'worldcam:30643', '84c35988b535734fc6': 'worldcam:836', '677c44787bd5bef7f6': 'worldcam:41082',
 'ce487723f8f8fb990a': 'youtube:SZEwLB6Dxks', '8844a34c51fe0be9b3': 'worldcam:37855', '1ae1826a4680277f85': 'worldcam:14769',
 '1fabafe8f9e1402de0': 'worldcam:7289', 'ea2a5e630b2e176aab': 'youtube:2O6gwr6chxw', '462b47aa540c21a233': 'worldcam:11704',
 # kontroll: nem jelölt réginek
 'de477eb9f1705a4a6f': 'worldcam:11713', '12e0db3df3bb3bdc0c': 'worldcam:10505',
}
JS = """async (id) => {
  const r = await fetch('/api/cam/' + id + '/image', {cache: 'no-store'});
  const h = {}; r.headers.forEach((v, k) => h[k] = v);
  const b = new Uint8Array(await r.arrayBuffer()); let s = '';
  for (let i = 0; i < b.length; i += 8192) s += String.fromCharCode.apply(null, b.subarray(i, i + 8192));
  let feat = null; try { const f = await fetch('/api/cam/' + id + '/feature'); feat = await f.text(); } catch (e) {}
  return {status: r.status, headers: h, b64: btoa(s), feature: feat && feat.slice(0, 3000)};
}"""
async def main():
    os.makedirs(f'{OUT}/img', exist_ok=True)
    res = {}
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36')
        pg = await ctx.new_page()
        await pg.goto('https://www.argosatlas.com/', wait_until='domcontentloaded', timeout=60000)
        await pg.wait_for_timeout(8000)
        for kor in (1, 2):
            for cid in REGI:
                try:
                    r = await pg.evaluate(JS, cid)
                    data = base64.b64decode(r.pop('b64'))
                    open(f'{OUT}/img/{cid}_{kor}.jpg', 'wb').write(data)
                    r['sha1'] = hashlib.sha1(data).hexdigest()[:12]; r['meret'] = len(data)
                except Exception as e:
                    r = {'hiba': str(e)[:300]}
                res.setdefault(cid, {})[f'argos{kor}'] = r
                await pg.wait_for_timeout(900)
            if kor == 1:
                await pg.wait_for_timeout(240000)
        # eredeti források
        for cid, src in REGI.items():
            if not src: continue
            kind, val = src.split(':', 1)
            info = {}
            try:
                if kind == 'youtube':
                    r = await ctx.request.get(f'https://i.ytimg.com/vi/{val}/hqdefault_live.jpg')
                    open(f'{OUT}/img/{cid}_ytlive.jpg', 'wb').write(await r.body()); info['ytlive_status'] = r.status
                    r = await ctx.request.get(f'https://www.youtube.com/watch?v={val}')
                    t = await r.text()
                    info['isLiveNow'] = re.findall(r'"isLiveNow":(true|false)', t)[:1]
                    info['isLive'] = re.findall(r'"isLiveContent":(true|false)', t)[:1]
                    info['title'] = re.findall(r'<title>(.*?)</title>', t)[:1]
                    info['playability'] = re.findall(r'"playabilityStatus":\{"status":"(\w+)"', t)[:1]
                else:
                    for url in (f'https://www.worldcam.eu/webcams/europe/hungary/{val}', f'https://www.worldcam.eu/webcam/{val}', f'https://www.worldcam.eu/{val}'):
                        q = await ctx.new_page()
                        try:
                            resp = await q.goto(url, wait_until='domcontentloaded', timeout=40000)
                            await q.wait_for_timeout(3000)
                            html = await q.content()
                            info[url] = {'status': resp.status if resp else None, 'final': q.url, 'title': await q.title(),
                                'img': re.findall(r'<img[^>]+src="([^"]+)"', html)[:25],
                                'iframe': re.findall(r'<iframe[^>]+src="([^"]+)"', html)[:10],
                                'linkek': [x for x in re.findall(r'href="([^"]+)"', html) if 'hungary' in x or 'http' in x][:40]}
                            if resp and resp.status == 200 and str(val) in q.url: break
                        except Exception as e:
                            info[url] = {'hiba': str(e)[:200]}
                        finally:
                            await q.close()
            except Exception as e:
                info['hiba'] = str(e)[:300]
            res[cid]['eredeti'] = info
        await b.close()
    json.dump(res, open(f'{OUT}/eredmeny.json', 'w'), ensure_ascii=False, indent=1)
asyncio.run(main())
