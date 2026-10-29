<!DOCTYPE html>
<html lang="hu">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Mr. Gabee – Küldd el nekem</title>
<meta name="description" content="Láttál valamit Csepelen vagy a környéken? Küldd el nekem a képet, videót vagy üzenetedet, névtelenül teszem ki.">
<meta name="theme-color" content="#071a22">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,700;12..96,800&family=Figtree:wght@400;500;600;700&display=swap">
<style>
/* Mr. Gabee – ugyanaz a sötét zöldeskék alap és türkiz kiemelés, mint a GitHubos „Írj nekem” oldalon. */
:root{
  --bg:#071a22; --card:rgba(255,255,255,.06); --field:rgba(0,0,0,.22); --line:rgba(255,255,255,.14); --text:#ffffff; --muted:#a3bcc4;
  --band:transparent; --band-2:transparent; --band-text:#ffffff; --band-muted:#c3d6dc;
  --acc:#2ee6d6; --acc-hover:#5ff0e3; --acc-text:#04252a; --acc-soft:rgba(46,230,214,.14); --acc-ink:#2ee6d6;
  --ok:#5cc98d; --ok-soft:rgba(92,201,141,.12); --err:#f2867f; --err-soft:rgba(242,134,127,.12);
  --f-display:"Bricolage Grotesque","Segoe UI",system-ui,sans-serif;
  --f-body:"Figtree",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;
  color-scheme:dark;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;min-height:100vh;background:radial-gradient(70% 50% at 0% 0%,#0d3a40 0%,transparent 70%),radial-gradient(80% 60% at 100% 100%,#0b2a4a 0%,transparent 70%),var(--bg);background-attachment:fixed;color:var(--text);font:16px/1.55 var(--f-body)}
a{color:inherit}
.wrap{max-width:880px;margin:0 auto;padding-left:max(18px,env(safe-area-inset-left));padding-right:max(18px,env(safe-area-inset-right))}
h1,h2,h3{font-family:var(--f-display);line-height:1.12;margin:0;text-wrap:balance;letter-spacing:-.015em}

/* fejléc */
.band{background:radial-gradient(90% 120% at 100% 0%,var(--band-2) 0%,transparent 62%),var(--band);color:var(--band-text)}
.bar{display:flex;align-items:center;gap:16px;padding-block:16px;flex-wrap:wrap}
.logo{display:flex;align-items:center;gap:10px;font-family:var(--f-display);font-weight:800;font-size:19px;letter-spacing:.08em;text-decoration:none}
.tile{width:38px;height:38px;border-radius:11px;display:grid;place-items:center;flex:none;background:linear-gradient(135deg,#2ee6d6,#12a39a);color:#04252a}
.tile svg{width:20px;height:20px}
.nav{margin-left:auto;display:flex;gap:18px;font-size:15px;flex-wrap:wrap}
.nav a{color:var(--band-muted);text-decoration:none}
.nav a:hover{color:#fff;text-decoration:underline}
.hero{padding-block:22px 40px;display:grid;gap:14px}
.hero h1{font-size:clamp(32px,6vw,52px);font-weight:800}
.hero h1 em{font-style:normal;background:linear-gradient(90deg,#2ee6d6,#9be86b);-webkit-background-clip:text;background-clip:text;color:transparent}
.hero p{margin:0;color:var(--band-muted);font-size:18px;max-width:58ch}
.actions{display:flex;flex-wrap:wrap;gap:12px;margin-top:8px}

.btn{font:600 16px/1 var(--f-body);display:inline-flex;align-items:center;justify-content:center;gap:9px;padding:15px 22px;border-radius:12px;border:1px solid transparent;cursor:pointer;text-decoration:none;transition:background .15s,border-color .15s,transform .1s}
.btn svg{width:18px;height:18px;flex:none}
.btn:active{transform:translateY(1px)}
.btn:focus-visible,input:focus-visible,textarea:focus-visible,summary:focus-visible{outline:3px solid #2ee6d6;outline-offset:2px}
.btn-primary{background:var(--acc);color:var(--acc-text)}
.btn-primary:hover{background:var(--acc-hover)}
.btn-ghost{background:var(--card);color:#fff;border-color:var(--line)}
.btn-ghost:hover{background:rgba(255,255,255,.1)}
.btn[disabled]{opacity:.7;cursor:progress}

main{padding-block:28px 48px;display:grid;gap:22px}

/* visszajelzés a PHP-tól */
.alert{padding:14px 16px;border-radius:12px;font-weight:600;border:1px solid}
.alert.success{background:var(--ok-soft);color:var(--ok);border-color:currentColor}
.alert.error{background:var(--err-soft);color:var(--err);border-color:currentColor}

.steps{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
@media (max-width:640px){.steps{grid-template-columns:1fr}}
.step{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;display:grid;gap:4px}
.step small{font-weight:700;font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--acc-ink)}
.step b{font-size:17px}
.step span{color:var(--muted);font-size:15px}

/* űrlapok */
details.panel{background:var(--card);border:1px solid var(--line);border-radius:16px;scroll-margin-top:16px}
details.panel[open]{border-color:var(--acc)}
summary{list-style:none;cursor:pointer;display:flex;align-items:center;gap:14px;padding:18px 20px;border-radius:16px}
summary::-webkit-details-marker{display:none}
summary .ic{width:42px;height:42px;border-radius:12px;display:grid;place-items:center;background:var(--acc-soft);color:var(--acc-ink);flex:none}
summary .ic svg{width:22px;height:22px}
summary h2{font-size:20px}
summary p{margin:2px 0 0;color:var(--muted);font-size:15px}
summary .chev{margin-left:auto;width:22px;height:22px;color:var(--muted);transition:transform .2s;flex:none}
details[open] summary .chev{transform:rotate(180deg)}
form{display:grid;gap:14px;padding:4px 20px 22px}
.row{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media (max-width:640px){.row{grid-template-columns:1fr}}
label{display:grid;gap:6px;font-weight:600;font-size:15px}
label .opt{font-weight:400;color:var(--muted)}
input[type=text],input[type=email],input[type=tel],textarea{width:100%;font:16px/1.4 var(--f-body);color:var(--text);background:var(--field);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
textarea{min-height:120px;resize:vertical}
input::placeholder,textarea::placeholder{color:var(--muted);opacity:.8}
.drop{position:relative;display:grid;place-items:center;text-align:center;gap:6px;padding:26px 16px;border:2px dashed var(--line);border-radius:14px;background:var(--field);cursor:pointer}
.drop:hover,.drop.over{border-color:var(--acc)}
.drop input{position:absolute;inset:0;opacity:0;cursor:pointer;width:100%}
.drop b{font-size:16px}
.drop span{color:var(--muted);font-size:14px}
.drop .chosen{color:var(--text);font-weight:600}
.hint{margin:0;color:var(--muted);font-size:14px}
.formerr{margin:0;color:var(--err);font-weight:600;font-size:15px}
.hp{position:absolute;left:-9999px;top:-9999px}

footer{border-top:1px solid var(--line);padding-block:20px 32px;color:var(--muted);font-size:14px}
footer .wrap{display:flex;flex-wrap:wrap;gap:8px 20px;align-items:center}
footer a{text-decoration:none}
footer a:hover{text-decoration:underline}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}

.chan{display:grid;gap:10px}
.chan a{display:flex;align-items:center;gap:14px;padding:14px 16px;border-radius:16px;background:var(--card);border:1px solid var(--line);text-decoration:none;min-width:0}
.chan a:hover{border-color:var(--acc)}
.chan .ci{width:42px;height:42px;border-radius:12px;display:grid;place-items:center;color:#fff;flex:none}
.chan .ci svg{width:22px;height:22px}
.chan span.t{display:grid;min-width:0}
.chan small{font-size:12px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}
.chan b{font-size:17px;overflow-wrap:anywhere}
.chan i{margin-left:auto;font-style:normal;color:var(--acc);font-size:20px}
.c-blue{background:linear-gradient(135deg,#3aa0ff,#2b6bff)}
.c-green{background:linear-gradient(135deg,#4cd964,#22a843)}
.c-teal{background:linear-gradient(135deg,#2ee6d6,#12a39a)}
.c-viber{background:linear-gradient(135deg,#8f5db7,#665cac)}
.label{font-size:13px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--acc)}
</style>
</head>
<body>

<header class="band">
  <div class="wrap">
    <div class="bar">
      <a class="logo" href="/"><span class="tile" aria-hidden="true"><svg viewBox="0 0 24 24" fill="currentColor"><circle cx="7" cy="12" r="1.8"/><circle cx="12" cy="12" r="1.8"/><circle cx="17" cy="12" r="1.8"/></svg></span>MR.GABEE</a>
      <nav class="nav" aria-label="Fő menü">
        <a href="#feltoltes" data-open="feltoltes">Beküldés</a>
        <a href="#elerhetoseg">Írj nekem</a>
        <a href="https://www.facebook.com/mrgabeeee" target="_blank" rel="noopener">Facebook</a>
      </nav>
    </div>
    <div class="hero">
      <h1>Láttál valamit a környéken? <em>Küldd el nekem!</em></h1>
      <p>Gabee vagyok, a Mr. Gabee Hírei oldalt én szerkesztem. Képet, videót vagy pár sort várok bármiről, ami Csepelen és környékén történik. Névtelenül teszem ki, és minden üzenetet elolvasok.</p>
      <div class="actions">
        <a class="btn btn-primary" href="#feltoltes" data-open="feltoltes"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 16V4m0 0-5 5m5-5 5 5M4 20h16"/></svg>Felvétel beküldése</a>
        <a class="btn btn-ghost" href="https://www.facebook.com/mrgabeeee" target="_blank" rel="noopener">Kövess a Facebookon</a>
      </div>
    </div>
  </div>
</header>

<main class="wrap">
  <?php if ($status_msg) echo '<div id="visszajelzes" tabindex="-1">' . $status_msg . '</div>'; ?>

  <details class="panel" id="feltoltes">
    <summary>
      <span class="ic" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="6" width="13" height="12" rx="2"/><path d="m16 10 5-3v10l-5-3"/></svg></span>
      <span><h2>Felvétel beküldése</h2><p>Egy kép vagy videó, 2 GB-ig. Regisztráció nélkül.</p></span>
      <svg class="chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m6 9 6 6 6-6"/></svg>
    </summary>
    <form id="uploadForm" method="POST" enctype="multipart/form-data">
      <div class="row">
        <label><span>Neved <span class="opt">(nem írom ki)</span></span><input type="text" name="nev" placeholder="Hogyan szólíthatlak?" required autocomplete="name"></label>
        <label><span>Helyszín</span><input type="text" name="helyszin" placeholder="Hol történt?" required></label>
      </div>
      <label><span>Mi történt? <span class="opt">(nem kötelező)</span></span><textarea name="leiras" placeholder="Pár szó az esetről…"></textarea></label>
      <label class="drop" id="drop">
        <input type="file" id="fileInput" name="media_file" required accept="image/*,video/*">
        <b>Fájl kiválasztása</b>
        <span id="fileInfo">Koppints ide, vagy húzd ide a képet, videót.</span>
      </label>
      <p class="formerr" id="uploadErr" hidden></p>
      <button type="submit" class="btn btn-primary" id="uploadBtn">Küldés</button>
      <p class="hint">Nagy videónál a feltöltés több percig is tarthat. Ne zárd be az oldalt, amíg a visszajelzés meg nem jelenik.</p>
    </form>
  </details>

  <details class="panel" id="uzenet">
    <summary>
      <span class="ic" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/></svg></span>
      <span><h2>Üzenet nekem</h2><p>Hír, tipp, kérdés. Minden üzenetet elolvasok.</p></span>
      <svg class="chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m6 9 6 6 6-6"/></svg>
    </summary>
    <form method="POST" id="msgForm">
      <input type="hidden" name="uzenet_kuldes" value="1">
      <div class="row">
        <label><span>Neved</span><input type="text" name="u_nev" placeholder="Hogyan szólíthatlak?" required autocomplete="name"></label>
        <label><span>Telefonszám <span class="opt">(nem kötelező)</span></span><input type="tel" name="u_tel" placeholder="+36 …" autocomplete="tel"></label>
      </div>
      <label><span>E-mail címed <span class="opt">(ha választ vársz)</span></span><input type="email" name="u_email" placeholder="nev@pelda.hu" autocomplete="email"></label>
      <label><span>Üzenet</span><textarea name="u_szoveg" placeholder="Írd le, mit láttál, hallottál…" required style="min-height:150px"></textarea></label>
      <button type="submit" class="btn btn-primary" id="msgBtn">Üzenet elküldése</button>
    </form>
  </details>

  <section id="elerhetoseg" style="display:grid;gap:12px">
    <span class="label">Így is elérsz</span>
    <div class="chan">
      <a href="https://m.me/104411308403346" target="_blank" rel="noopener"><span class="ci c-blue" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3C7 3 3 6.7 3 11.3c0 2.6 1.3 4.9 3.3 6.4V21l3-1.7c.9.3 1.8.4 2.7.4 5 0 9-3.7 9-8.3S17 3 12 3z"/><path d="m7 13 3.5-3.5 2.5 2.5 4-4"/></svg></span><span class="t"><small>Messenger</small><b>Üzenet a Facebook-oldalnak</b></span><i aria-hidden="true">→</i></a>
      <a href="https://wa.me/36707540254" target="_blank" rel="noopener"><span class="ci c-green" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20l1.4-4A8 8 0 1 1 8.2 19z"/><path d="M9 9.5c0 3 2.5 5.5 5.5 5.5l1-1.5-2-1-1 .8a4 4 0 0 1-1.8-1.8l.8-1-1-2z"/></svg></span><span class="t"><small>WhatsApp</small><b>+36 70 754 0254</b></span><i aria-hidden="true">→</i></a>
      <a href="viber://chat?number=%2B36707540254"><span class="ci c-viber" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3c5 0 8 2.5 8 7.5S17 18 12 18l-4 3v-3.5C5.5 16.5 4 14 4 10.5 4 5.5 7 3 12 3z"/><path d="M9.5 8.5c.3 2.4 1.6 3.7 4 4l1-1.2 1.6.8-.6 1.6c-3.5-.2-6.2-2.9-6.4-6.4l1.6-.6.8 1.6z"/></svg></span><span class="t"><small>Viber</small><b>+36 70 754 0254</b></span><i aria-hidden="true">→</i></a>
      <a href="mailto:olvaso@mrgabee.hu"><span class="ci c-teal" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/></svg></span><span class="t"><small>E-mail</small><b>olvaso@mrgabee.hu</b></span><i aria-hidden="true">→</i></a>
    </div>
    <p class="hint">A beküldött anyagokat névtelenül teszem ki, a durva szavakat finomítom.</p>
  </section>
</main>

<footer>
  <div class="wrap">
    <span>Mr.Gabee · Csepel és környéke</span>
    <a href="https://www.facebook.com/mrgabeeee" target="_blank" rel="noopener">Facebook</a>
    <a href="#uzenet" data-open="uzenet">Írj nekem</a>
  </div>
</footer>

<script>
(function () {
  var limit = <?php echo $max_file_size_bytes; ?>;
  var form = document.getElementById('uploadForm');
  var input = document.getElementById('fileInput');
  var info = document.getElementById('fileInfo');
  var err = document.getElementById('uploadErr');
  var drop = document.getElementById('drop');

  function meret(b) { return b >= 1073741824 ? (b / 1073741824).toFixed(1) + ' GB' : b >= 1048576 ? (b / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(b / 1024)) + ' KB'; }
  function osszeg() { var t = 0; for (var i = 0; i < input.files.length; i++) t += input.files[i].size; return t; }

  input.addEventListener('change', function () {
    err.hidden = true;
    var n = input.files.length;
    if (!n) { info.textContent = 'Koppints ide, vagy húzd ide a képet, videót.'; info.className = ''; return; }
    info.textContent = input.files[0].name + ' (' + meret(osszeg()) + ')';
    info.className = 'chosen';
  });
  ['dragenter', 'dragover'].forEach(function (e) { drop.addEventListener(e, function () { drop.classList.add('over'); }); });
  ['dragleave', 'drop'].forEach(function (e) { drop.addEventListener(e, function () { drop.classList.remove('over'); }); });

  form.addEventListener('submit', function (e) {
    if (osszeg() > limit) {
      e.preventDefault();
      err.textContent = 'A fájl ' + meret(osszeg()) + ', ez több a megengedett 2 GB-nál. Válassz kisebb fájlt.';
      err.hidden = false;
      return;
    }
    var b = document.getElementById('uploadBtn');
    b.disabled = true;
    b.textContent = 'Feltöltés folyamatban…';
  });
  document.getElementById('msgForm').addEventListener('submit', function () {
    var b = document.getElementById('msgBtn'); b.disabled = true; b.textContent = 'Küldés…';
  });

  // A gombok és menüpontok kinyitják a megfelelő panelt.
  function nyit(id) {
    var d = document.getElementById(id);
    if (!d) return;
    document.querySelectorAll('details.panel').forEach(function (x) { if (x !== d) x.open = false; });
    d.open = true;
    d.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  document.querySelectorAll('[data-open]').forEach(function (a) {
    a.addEventListener('click', function (e) { e.preventDefault(); nyit(a.getAttribute('data-open')); history.replaceState(null, '', '#' + a.getAttribute('data-open')); });
  });
  var v = document.getElementById('visszajelzes');
  if (v) { v.scrollIntoView({ block: 'center' }); v.focus({ preventScroll: true }); }
  else if (location.hash === '#feltoltes' || location.hash === '#uzenet') nyit(location.hash.slice(1));
  window.addEventListener('hashchange', function () { if (location.hash === '#feltoltes' || location.hash === '#uzenet') nyit(location.hash.slice(1)); });
})();
</script>
</body>
</html>
