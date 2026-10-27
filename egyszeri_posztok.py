"""
📌 Egyszeri, adott napra ütemezett posztok (Gábor jóváhagyásával).
A szines_posztok.py MENETREND-jéből hívva: csak a megadott napon ad szöveget.
"""

from datetime import date

POSZTOK = {
    "bkk_soroksar": (date(2026, 10, 19), """🚌 KÖZVETLEN BUSZ A BELVÁROSBA? ÚJ BKK-JAVASLAT DÉL-PESTNEK 🚌

Beleástam magam a BKK egyik friss anyagába, ami a környékünk buszhálózatát érinti. Fontos: ez egyelőre csak javaslat, még semmi nem dőlt el, de érdemes tudni róla.

Mi a lényeg?

🟠 66-os buszcsalád (66, 66B, 66E): Soroksár felől a Határ út helyett továbbmenne a belvárosba, a Boráros térre, egyes változatokban egészen a Kálvin térig. A BKK számítása szerint a Kálvin térig akár 12 percet, az Újbuda-központig 9, a Deák térig 7 percet lehetne nyerni.
🟤 148-as busz (Csepel): Kőbánya-Kispest helyett a Határ úti metrómegállóig járna, így gyorsabban elérné a metrót.
🟢 119-es és 🟣 166-os: Wekerletelepen át Kőbánya-Kispestig járnának, a 119-es sűrűbben.
🔴 54-es: rövidebb lenne, Péterimajort és a Víztorony teret a 166-os szolgálná ki.

Három változat van:
1️⃣ a 66-osok mindig csak a Boráros térig mennek,
2️⃣ csúcsidőben a Kálvin térig, egyébként a Boráros térig,
3️⃣ munkanapokon reggel 6 és este 9 között a Kálvin térig.

A BKK napi 500-1000 utassal többel számol, és őszintén leírja a hátulütőket is: egyes utakon újabb átszállás jöhet, és Wekerletelepen ritkább lehet a busz. A 148-asról a Kőbánya-Kispesti közvetlen kapcsolat is megszűnne.

Hol tart? A tervet most véleményezik, és ha továbbmegy, a csepeli, pesterzsébeti és kispesti kapcsolatok miatt szélesebb egyeztetés és társadalmi egyeztetés is jön. Kell hozzá egy bővített buszforduló is, és a pénz is kérdés: évente 65-160 millió forint.

💬 Ti hogy látjátok? Jól jönne a közvetlen belvárosi busz, vagy inkább a 148-as Kőbánya-Kispesti kapcsolatát hiányolnátok? Írjátok meg kommentben!

📄 A BKK teljes tájékoztatója:
https://einfoszab.budapest.hu/File/DownloadDvD/131522?filename=Tajekoztato%20Soroksar%20autobuszkozlekedes%20fejlesztesenek%20lehetosegerol_KKVB_260922_alairt.pdf&prevcont=Session&prevaction=DvdItem&path=Tev%C3%A9kenys%C3%A9gre,%20m%C5%B1k%C3%B6d%C3%A9sre%20vonatkoz%C3%B3%20adatok%20%2F%20D%C3%B6nt%C3%A9shozatal,%20%C3%BCl%C3%A9sek%20%2F%20A%20F%C5%91v%C3%A1rosi%20K%C3%B6zgy%C5%B1l%C3%A9s%20bizotts%C3%A1gainak%20%C3%BCl%C3%A9sei&type=5&key=fovarosi-kozgyules-bizottsagainak-nyilvanos-ulesei&fileId=217403&sessionType=4&organizationtype=2&parentId=18580&parenttype=2

#Csepel #Pesterzsébet #Soroksár #BKK #közlekedés #148"""),
    "bombariado": (date(2026, 10, 19), """⚠️ BOMBARIADÓ EGY CSEPELI ISKOLÁBAN ⚠️

Az értesüléseim szerint Csepelen, a Tejút utca egyik iskolájában bombariadó van. Részleteket egyelőre nem tudok.

Kedves szülők: őrizzétek meg a nyugalmatokat, és kövessétek az iskola és a hatóságok utasításait. Aki teheti, kerülje el a környéket, hogy ne zavarjuk a mentesítést.

❓ Ha tudsz részleteket, írd meg kommentben vagy üzenetben, és frissítem a bejegyzést.

#Csepel #bombariadó #Tejútutca"""),
    "ecofamily": (date(2026, 10, 21), """🛒 JÖN AZ ECOFAMILY CSEPELRE? 🛒

Egyik olvasóm utánajárt valaminek, ami szerintem sokakat érdekel: lesz-e EcoFamily bolt Csepelen. Ő és több csepeli ismerőse is szereti a láncot, de a meglévő üzleteket csak nagy kerülővel lehet megközelíteni innen.

Írt nekik, és pár levélváltás után a cég hálózatfejlesztési vezetőjétől ezt a választ kapta:

„Szeretném jelezni, hogy dolgozunk a csepeli üzletnyitáson. Addig is várjuk a többi budapesti üzletünkben.”

Konkrét címet és dátumot egyelőre nem írtak, de úgy tűnik, Csepel is szóba került. Ha többet megtudok, szólok!

💬 Ti mit szólnátok egy csepeli EcoFamilyhez? Hová tennétek, hol lenne a legjobb helye? Írjátok meg kommentben!

#Csepel #EcoFamily #boltnyitás #olvasóihír"""),
    "heimpal_20261023": (date(2026, 10, 23), """❤️ MA 97 ÉVE HUNYT EL DR. HEIM PÁL ❤️

Ma 97 éve, 1929. október 23-án, mindössze 54 évesen hunyt el Dr. Heim Pál, a magyar csecsemő- és gyermekgyógyászat egyik legnagyobb alakja.

Egész életét a gyerekek gyógyításának szentelte. Számára a beteg gyerek sosem csak egy eset volt, hanem egy egész kis világ, amelynek figyelem, szeretet és remény kell. Fiatalon, 16 évesen veszítette el a húgát agyhártyagyulladásban, és ez a fájdalom vitte arra az útra, amelyen végig haladt: hogy megelőzze a gyermekhalált, enyhítse a kicsik szenvedését, és reményt adjon a szülőknek.

👩‍⚕️ Az általa nevelt „Heim nővérek” generációkon át vitték tovább a szemléletét, és ez ma is él a gyermekellátásban. Az ő mondata ma is érvényes: a gyermek méltósága sérthetetlen!

🏥 A nevét viselő Heim Pál Országos Gyermekgyógyászati Intézet ma is hálával őrzi az emlékét. Sok csepeli és erzsébeti család is köszönhet nekik egy gyógyulást, egy átvirrasztott éjszaka utáni megkönnyebbülést.

🕯️ Tisztelettel emlékezem rá.

#HeimPál #gyermekgyógyászat #emlékezés #Csepel #Pesterzsébet"""),
    "kaszkador_20261023": (date(2026, 10, 23), """🚗🔥 KASZKADŐR SHOW LESZ CSEPELEN A HÉTVÉGÉN! 🔥🚗

Ha füstös, hangos, látványos családi programot kerestek hétvégére, ezt nem érdemes kihagyni: lángok, csikorgó kerekek, roncsautók és egy hatalmas Monster Truck, mindez pár méterről!

📍 Helyszín: a csepeli Tesco parkolója (II. Rákóczi Ferenc út 191.)
📅 Szombat (október 24.) és vasárnap (október 25.)
🚪 Kapunyitás 14:30-kor, a műsor 15:00-kor kezdődik

💥 A programban:
🦖 Monster Truck, ami simán átgázol a roncsautókon
🌀 Drift és autós mutatványok, centire pontos pörgésekkel
🔥 Kaszkadőrakciók: ugrások, esések, lángoló jelenetek

🎁 A gyerekeknek külön meglepetés: az előadás végén mindegyiküket ingyen elviszik egy körre a Monster Truckkal!

🎟️ Jegyet a helyszínen, a kapunál lehet venni.
🌐 Részletek: https://kaszkadorshow.hu

#Csepel #hétvége #családiprogram #kaszkadőrshow"""),
    "hev_ajto_20261022": (date(2026, 10, 22), """🚆 OLVASÓI LEVÉL: ORRA ELŐTT CSUKÓDOTT BE A HÉV AJTAJA 🚆

Egy olvasóm írta meg, hogy ma reggel két gyerekkel akart felszállni a HÉV-re a csepeli végállomáson, amikor a kisebbik gyerek előtt becsukódott az ajtó. A kicsi nagyon megijedt.

💛 Szerencsére nem maradt egyedül: a Fornetti dolgozói étellel, itallal kínálták, és több utas is észrevette, mi történt, és mellette maradt. Az olvasóm ezúton is köszöni nekik, és én is csatlakozom: mennyire jó fejek vagytok!

👀 Kérem a HÉV-vezetőket, hogy induláskor különösen figyeljenek a gyerekekkel utazókra, nekünk utasoknak pedig érdemes kézen fogva, egyszerre felszállni a kicsikkel.

#Csepel #HÉV #olvasóilevél #összefogás"""),
    "bankkartya_20261022": (date(2026, 10, 22), """💳 BANKKÁRTYÁT FELEJTETT VALAKI AZ ATM-BEN 💳

Ma valaki a Zrínyi utcai ATM-ben hagyta a bankkártyáját, és egy becsületes megtaláló keresi a tulajdonost. Ha te voltál, írj neki itt: https://www.facebook.com/profile.php?id=100007173042045
Addig is érdemes a bankodnál letiltatni a kártyát, a biztonság kedvéért.

🙏 Köszönet a megtalálónak, hogy nem ment el mellette!

#Csepel #elveszett #bankkártya #talált"""),
    "busz159_20261022": (date(2026, 10, 22), """🚍 BALESET A 159-ES BUSZ ÚTVONALÁN 🚍

Úgy értesültem, hogy a 159-es busz érintett volt egy balesetben, amelyben egy embert elütöttek. Hogy pontosan mi történt és hogyan, egyelőre nem tudom.

⚠️ A 159-es egy ideig terelve közlekedett, és nem érintette a Kossuth Lajos utca / Erdősor utca megállót. Ha arra vártok buszra, figyeljétek a kiírásokat, még előfordulhat késés!

🙏 Remélem, a sérült mihamarabb rendbe jön.

💬 Ha többet tudsz, láttad, vagy épp a buszon ültél, írd meg kommentben, vagy keress meg az elérhetőségeimen!

#Csepel #Pesterzsébet #159esbusz #baleset #BKV #közlekedés"""),
    "dugo_20261021": (date(2026, 10, 21), """🚨 HATALMAS A DUGÓ CSEPEL FELÉ 🚨

Aki teheti, most messziről kerülje el a Csepelre vezető utakat! A bevezető szakaszokon nagy a torlódás, és a buszok is jelentős késéssel közlekednek.

Ha nem muszáj most elindulni, érdemes kicsit várni, a buszra várók pedig számoljanak több idővel.

💬 Ti hol álltok éppen? Írjátok meg kommentben, hol a legrosszabb a helyzet, hogy a többiek is tudják, mire számítsanak!

#Csepel #dugó #közlekedés #torlódás"""),
    "dugo_20261027": (date(2026, 10, 27), """🚗 ÁLL A SOR A WEISS MANFRÉD ÚTON 🚗

Ma reggel komoly a torlódás Csepelen: a Szent Imre tértől áll a sor a Weiss Manfréd úton a belváros felé.

Ha arra indulsz, számolj több idővel, vagy ha teheted, válassz másik útvonalat. A buszok is késhetnek ezen a szakaszon.

💬 Ti most hol jártok? Írjátok meg kommentben, meddig ér a sor, és mikor indul meg, hogy a többiek is tudják, mire számítsanak!

#Csepel #dugó #közlekedés #WeissManfrédút"""),
    "mentok_20261027": (date(2026, 10, 27), """🚑 A MENTŐS POSZT UTÁN: KÉT ÚJABB OLVASÓI ÜZENET

A mentős várakozásról szóló bejegyzés után valóságos áradatként érkeztek az üzenetek az elérhetőségeimre. Előre szeretnék tisztázni valamit: nagyon sok mentős barátom van, és mindegyiküket úgy szeretem, mintha a testvérem lenne. A bejegyzéssel egy pillanatig sem akartam a mentősöket lejáratni. Minden tiszteletem az övék, és tudom, mekkora terhelés alatt dolgoznak nap mint nap. ❤️

Két üzenetet mégis megosztok név nélkül, mert a téma két különböző oldalát mutatják meg.

✉️ AZ ELSŐ OLVASÓ:
„Tavaly az apósomhoz hívott mentőt az anyósom. A mentő csak sokára ért ki: a párom közben vidékről hazaért a munkából, és akkor fordult be az utcába a mentőautó. A mentős megkérdezte, hogy már egy lábköröm-beszakadás miatt is mentőt hívnak. A kórháznál az apósomnak nem segítettek kiszállni, majdnem kiesett az autóból, a párom rohant oda, hogy segítsen. Az apósom két hónappal később a kórházban meghalt.
Maximálisan elhiszem, hogy ők is túl vannak terhelve, de ha már ennyi idő után kiérnek, jó lenne, ha azt, aki fél és fájdalmai vannak, legalább egy kis kedvesség fogadná. Köszönöm, hogy megírhattam.”

✉️ A MÁSODIK OLVASÓ:
„Sajnos sokan teljesen indokolatlanul hívnak mentőt, és ahová tényleg kellene, oda nem tudnak kimenni. A háromórás várakozás oka sokszor az, hogy a legközelebbi szabad kocsi mondjuk Vácon van, és azt riasztják.”

💡 A két üzenet jól mutatja, hogy a gond nem egy-egy emberen múlik: kevés a szabad mentőautó, sok a nem indokolt hívás, és ennek a sürgős esetekben élők látják kárát. Ezért is fontos, hogy a 112-t és a 104-et csak valódi vészhelyzetben hívjuk. Nem sürgős panasszal az ügyeletet vagy a háziorvost érdemes keresni.

Nektek milyen tapasztalatotok van? Kérlek, írjátok meg kommentben, de tiszteljük egymást és a mentősöket is! 🙏

#Csepel #Pesterzsébet #mentők #olvasóilevél"""),
    "oraallitas_20261025": (date(2026, 10, 25), """🕒 ÉJJEL VISSZAÁLLT AZ ÓRA – ITT A TÉLI IDŐSZÁMÍTÁS 🕒

Ha ma reggel furcsán korán ébredtél, nem tévedés: hajnali 3 órakor visszaállítottuk az órákat 2 órára, így ma egy órával többet aludhattunk. 😴

📱 A telefon, az okosóra és a számítógép magától átállt.
⏰ A sütő, a mikró, a falióra és az autó órája viszont valószínűleg még a nyári időt mutatja, ezeket érdemes most átállítani.

🌆 Mostantól jóval korábban sötétedik, délután fél 5 körül már szürkül. Kérlek, figyeljetek jobban egymásra az utakon: gyalogosként és biciklisként érdemes valami világosat vagy fényvisszaverőt viselni, autósként pedig számítsatok rájuk.

A téli időszámítás 2027. március 28-ig tart, akkor tekerjük majd előre az órát.

Szép vasárnapot kívánok mindenkinek! ☕

#Csepel #óraátállítás #téliidőszámítás"""),
}


def szoveg(kulcs, nap):
    datum, s = POSZTOK[kulcs]
    return s if nap == datum else ""
