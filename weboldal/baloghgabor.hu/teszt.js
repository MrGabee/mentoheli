// A baloghgabor.hu ellenőrzése a szerveren: betöltés, kép, PDF, téma, és ha kérjük, valódi teszt-üzenet.
const { chromium } = require('playwright');
const fs = require('fs');
const [url, ki, valodi] = process.argv.slice(2);
(async () => {
  const b = await chromium.launch(); let ok = true; const hiba = m => { ok = false; console.log('HIBA:', m); };
  fs.mkdirSync(ki, { recursive: true });
  for (const [nev, vp] of [['gep', { width: 1280, height: 900 }], ['tel', { width: 390, height: 844 }]]) {
    const p = await b.newPage({ viewport: vp }); const jsh = []; p.on('pageerror', e => jsh.push(e.message));
    const r = await p.goto(url, { waitUntil: 'networkidle' }); console.log(nev, 'HTTP', r.status()); if (r.status() !== 200) hiba('HTTP ' + r.status());
    const kep = await p.$eval('.photo img', i => i.complete && i.naturalWidth > 0).catch(() => false); console.log(nev, 'profilkép betöltve:', kep); if (!kep) hiba('profilkép');
    console.log(nev, 'mezők:', await p.$$eval('#urlap [name]', e => e.map(x => x.name).join(',')));
    const sw = await p.evaluate(() => document.documentElement.scrollWidth); if (sw > vp.width) hiba('vízszintes görgetés ' + sw);
    await p.click('#temaGomb'); await p.waitForTimeout(200); console.log(nev, 'téma gomb után:', await p.evaluate(() => document.documentElement.getAttribute('data-theme')));
    await p.click('#temaGomb');
    await p.screenshot({ path: `${ki}/${nev}.png`, fullPage: true });
    if (jsh.length) hiba('JS: ' + jsh.join('; ')); await p.close();
  }
  const pdf = await (await b.newPage()).request.get(new URL('oneletrajz.pdf', url).href); console.log('PDF HTTP', pdf.status()); if (pdf.status() !== 200) hiba('PDF');
  if (valodi === 'igen') {
    const p = await b.newPage({ viewport: { width: 390, height: 844 } }); await p.goto(url, { waitUntil: 'networkidle' });
    await p.fill('[name=from_name]', 'TESZT – arculatcsere ellenőrzés (törölhető)');
    await p.fill('[name=reply_to]', 'uzenet@baloghgabor.hu');
    await p.fill('[name=subject]', 'TESZT – az új weboldal űrlapja');
    await p.fill('[name=message]', 'Automatikus teszt az új weboldal kapcsolati űrlapjához. Nyugodtan töröld.');
    await p.click('#kuldes'); await p.waitForSelector('#urlapUzenet:not([hidden])', { timeout: 30000 });
    const v = (await p.textContent('#urlapUzenet')).trim(); console.log('ŰRLAP válasz:', v); if (!/Köszönöm/.test(v)) hiba('űrlap: ' + v);
    await p.screenshot({ path: `${ki}/urlap_valasz.png` });
  }
  await b.close(); console.log(ok ? 'EREDMÉNY: MINDEN RENDBEN' : 'EREDMÉNY: HIBA'); process.exit(ok ? 0 : 1);
})();
