# mrgabee.hu kezdőlap

Az élő `index.php` két részből áll:

1. **PHP rész** (beállítások, Drive-feltöltés, levélküldés). Ez csak a szerveren van,
   jelszavakat tartalmaz, ezért nem kerül a repóba.
2. **HTML rész**: ez a `sablon.php`.

A `.github/workflows/weboldal_telepites.yml` letölti az élő index.php-t, levágja a régi
HTML részt, és a `sablon.php`-t teszi a helyére. A `mod.txt` mondja meg, mi történjen:

| mod.txt | Hatás |
| --- | --- |
| `proba` | `index_proba.php` néven kerül fel, az élő oldal nem változik |
| `eles` | lecseréli az `index.php`-t (az eredetit egyszer `index_elozo.php`-ként elmenti) |
| `torles` | leszedi az `index_proba.php`-t |

Ha a `valodi_teszt.txt` tartalma `igen`, a teszt valódi feltöltést és üzenetet is küld
(„TESZT – arculatcsere ellenőrzés” névvel), és a szerver válaszát ellenőrzi.
