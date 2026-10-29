// Az élő szerveren futó oldal ellenőrzése: mezők, panelek, és ha kérjük,
// valódi teszt-beküldés (feltöltés + üzenet), a szerver válaszával együtt.
const { chromium } = require('playwright');
const fs = require('fs');
const [url, ki, valodi] = process.argv.slice(2);
(async () => {
  const b = await chromium.launch();
  let ok = true;
  const hiba = m => { ok = false; console.log('HIBA:', m); };
  fs.mkdirSync(ki, { recursive: true });
  for (const [nev, vp] of [['gep', { width: 1280, height: 900 }], ['tel', { width: 390, height: 844 }]]) {
    const p = await b.newPage({ viewport: vp });
    const jsHibak = [];
    p.on('pageerror', e => jsHibak.push(e.message));
    const r = await p.goto(url, { waitUntil: 'networkidle' });
    console.log(nev, 'HTTP', r.status());
    if (r.status() !== 200) hiba('HTTP ' + r.status());
    const mezok = await p.$$eval('form', fs => fs.map(f => [...f.elements].map(e => e.name).filter(n => n).sort().join(',')));
    console.log(nev, 'űrlapok:', JSON.stringify(mezok));
    const sw = await p.evaluate(() => document.documentElement.scrollWidth);
    if (sw > vp.width) hiba(nev + ' vízszintes görgetés: ' + sw);
    await p.screenshot({ path: `${ki}/${nev}.png`, fullPage: true });
    await p.click('.actions .btn-primary');
    await p.waitForTimeout(500);
    if (!(await p.$eval('#feltoltes', d => d.open))) hiba(nev + ' a feltöltés panel nem nyílik');
    if (jsHibak.length) hiba(nev + ' JS hiba: ' + jsHibak.join('; '));
    await p.close();
  }
  if (valodi === 'igen') {
    fs.writeFileSync('/tmp/teszt_kep.png', Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==', 'base64'));
    const p = await b.newPage({ viewport: { width: 390, height: 844 } });
    await p.goto(url);
    await p.click('.actions .btn-primary');
    await p.fill('input[name=nev]', 'TESZT – arculatcsere ellenőrzés (törölhető)');
    await p.fill('input[name=helyszin]', 'Teszt, nem valódi esemény');
    await p.fill('textarea[name=leiras]', 'Automatikus teszt az új weboldal ellenőrzéséhez. Nyugodtan töröld.');
    await p.setInputFiles('#fileInput', '/tmp/teszt_kep.png');
    await p.waitForTimeout(3000);
    await Promise.all([p.waitForNavigation({ timeout: 300000 }), p.click('#uploadBtn')]);
    const v1 = await p.$('#visszajelzes') ? (await p.textContent('#visszajelzes')).trim() : '(nincs visszajelzés)';
    console.log('FELTÖLTÉS válasz:', v1);
    if (!/Siker/.test(v1)) hiba('feltöltés: ' + v1);
    await p.screenshot({ path: `${ki}/feltoltes_valasz.png` });
    await p.goto(url + '#uzenet');
    await p.waitForTimeout(500);
    await p.fill('input[name=u_nev]', 'TESZT – arculatcsere ellenőrzés (törölhető)');
    await p.fill('textarea[name=u_szoveg]', 'Automatikus teszt az új weboldal üzenetküldőjéhez. Nyugodtan töröld.');
    await p.waitForTimeout(3000);
    await Promise.all([p.waitForNavigation({ timeout: 120000 }), p.click('#msgBtn')]);
    const v2 = await p.$('#visszajelzes') ? (await p.textContent('#visszajelzes')).trim() : '(nincs visszajelzés)';
    console.log('ÜZENET válasz:', v2);
    if (!/elküldve/.test(v2)) hiba('üzenet: ' + v2);
    await p.screenshot({ path: `${ki}/uzenet_valasz.png` });
  }
  await b.close();
  console.log(ok ? 'EREDMÉNY: MINDEN RENDBEN' : 'EREDMÉNY: HIBA');
  process.exit(ok ? 0 : 1);
})();
