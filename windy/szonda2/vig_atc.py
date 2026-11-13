"""Ideiglenes: Vigilyst magyar kamerái + All Traffic Cams határkamerák forrása."""
import json, re
from playwright.sync_api import sync_playwright
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
ki = {}
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_context(user_agent=UA).new_page()
    page.goto('https://vigilyst.com/', wait_until='domcontentloaded', timeout=45000)
    page.wait_for_timeout(5000)
    r = page.evaluate("""async () => {
        const ni = await (await fetch('/api/cams?src=netindex')).json();
        const pts = await (await fetch('/api/cams?src=pts')).text();
        return {ni, pts};
    }""")
    ni = r['ni']
    ki['netindex_hu'] = [n for n in ni.get('nets', []) if re.search(r'hungar|ungarn|magyar|\\bHU\\b', json.dumps(n, ensure_ascii=False), re.I)]
    ki['netindex_db'] = len(ni.get('nets', []))
    ki['netindex_minta'] = ni.get('nets', [])[:3]
    ki['netindex_kulcsok'] = list(ni.keys())
    pts = json.loads(r['pts'])
    ki['pts_kulcsok'] = list(pts.keys())
    ki['pts_M_hu'] = [m for m in pts.get('M', []) if re.search(r'hungar|ungarn|magyar', json.dumps(m, ensure_ascii=False), re.I)]
    for k, v in pts.items():
        if isinstance(v, list) and len(v) > 50:
            ki.setdefault('pts_listak', {})[k] = [len(v), v[:3]]
    # HU dobozba eső pontok
    hu = []
    def jar(o):
        if isinstance(o, list):
            nums = [x for x in o if isinstance(x, (int, float))]
            if len(nums) >= 2:
                for a, c in ((nums[0], nums[1]), (nums[1], nums[0])):
                    if 45.7 <= a <= 48.6 and 16.1 <= c <= 22.9:
                        hu.append(o); return
            for x in o: jar(x)
        elif isinstance(o, dict):
            for x in o.values(): jar(x)
    jar(pts)
    ki['pts_hu_db'] = len(hu)
    ki['pts_hu_minta'] = hu[:60]
    for u in ['https://alltrafficcams.com/live/border-crossings/serbia/hungary/roszke-horgos/',
              'https://alltrafficcams.com/live/border-crossings/serbia/hungary/tompa-kelebija/',
              'https://alltrafficcams.com/live/border-crossings/austria/hungary/nickelsdorf-hegyeshalom/']:
        media = []
        page.on('request', lambda q: media.append(q.url) if re.search(r'm3u8|mjpg|mjpeg|\\.jpg|\\.mp4|stream|youtube|cam', q.url, re.I) else None)
        try:
            page.goto(u, wait_until='domcontentloaded', timeout=45000); page.wait_for_timeout(9000)
            ki[u] = {'cim': page.title(),
                     'iframe': page.eval_on_selector_all('iframe', 'e => e.map(x => x.src)'),
                     'video': page.eval_on_selector_all('video, video source', 'e => e.map(x => x.src)'),
                     'media': [m for m in dict.fromkeys(media) if 'google' not in m][:50]}
        except Exception as e:
            ki[u] = str(e)[:300]
    b.close()
json.dump(ki, open('windy/szonda2/vig_atc.json', 'w'), ensure_ascii=False, indent=1)
