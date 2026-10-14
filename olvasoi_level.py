"""
✉️ Egyszeri olvasói levél (a NAPOK-ban megadott napon megy ki, napközben).
"""

from datetime import date

NAPOK = {date(2026, 10, 15)}

LEVEL = """✉️ OLVASÓI LEVÉL: SZÁGULDOZÁS AZ ERDŐSOR UTCÁBAN ✉️
••••••••••••••••••••••••

Egy olvasóm írt nekem a csepeli Erdősor utca miatt. Változtatás nélkül közlöm a levelét:

„A környéken lakók nevében szeretném a figyelmüket kérni egy súlyos és folyamatosan fennálló csepeli közlekedési probléma nyilvánosságra hozatalában.

A múlt héten hivatalos megkereséssel fordultam a BRFK XXI. Kerületi Rendőrkapitányságához a 21. kerületi Erdősor utca (181–195. szám közötti szakasz) rendszeres gyorshajtásai és az ebből adódó veszélyhelyzetek miatt. Sajnos a rendőrségtől a mai napig nem érkezett válasz vagy intézkedés.
Az Erdősor utcában a helyzet napról napra tarthatatlanabb. A száguldozó járművek nemcsak az út szélén szabályosan parkoló autókban okoznak rendszeresen anyagi károkat, hanem a gyalogosokat és a szabályosan közlekedőket is közvetlen veszélynek teszik ki. A héten magam is alig tudtam elkerülni egy balesetet, amikor elsőbbségadási kötelezettség ellenére majdnem belém jöttek, és még a szabálytalankodónak állt feljebb.
Emellett a csúcsforgalomban és az esti órákban felpörgetett motorok és a folyamatos dudálás a környéken élő családok, kisgyermekes szülők mindennapjait is megnehezítik (egy pici gyermek mellett az altatást is komolyan hátráltatják a türelmetlen sofőrök).
Bízom benne, hogy a nyilvánosság erejével sikerül felhívni a figyelmet a helyzet súlyosságára, és végre érdemi intézkedésre (pl. rendszeres traffipaxos ellenőrzésre vagy sűrített járőrszolgálatra) ösztönözni az illetékeseket.
Mellékelten küldöm a rendőrségnek eljuttatott eredeti levelemet:

»Tisztelt BRFK XXI. Kerületi Rendőrkapitányság!

Ezúton szeretném felhívni a figyelmüket a XXI. kerületi Erdősor utcában (181-195) tapasztalható rendszeres és súlyos gyorshajtásokra.
A környéken lakóként nap mint nap azt tapasztalom, hogy a járművezetők jelentős része figyelmen kívül hagyja a megengedett sebességhatárokat. A fokozott sebesség miatt a gyalogosforgalom veszélyeztetve van, emellett a száguldó autók miatt az út szélén szabályosan parkoló gépjárművekben is rendszeresen keletkeznek anyagi károk.

Tisztelettel kérem Önöket, hogy a lakosság biztonsága és a rend fenntartása érdekében mérlegeljék sebességmérés (traffipax) kihelyezését, illetve a járőrellenőrzések sűrítését a megjelölt útszakaszon (különösen a csúcsforgalmi és esti időszakokban).

Együttműködésüket és intézkedésüket előre is köszönöm!

Tisztelettel,
K. Viktor«”

Köszönöm Viktornak, hogy megírta. Ti mit tapasztaltok az Erdősor utcában? Írjátok meg kommentben!
#Csepel #Erdősorutca #gyorshajtás #olvasóilevél"""


def szoveg(nap):
    return LEVEL if nap in NAPOK else ""
