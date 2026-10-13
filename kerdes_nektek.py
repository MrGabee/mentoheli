"""
💬 Kérdés nektek – napi beszélgetésindító kérdés a követőknek
A kérdések sorban jönnek (a dátum alapján), így amíg el nem fogynak,
nem ismétlődnek. Új kérdést a lista végére lehet írni.
"""

from poszt_valtozatos import Stilus

KERDESEK = [
    "Melyik a kedvenc helyetek Csepelen, Pesterzsébeten vagy Miklóson?",
    "Hol isszátok a legjobb kávét a környéken?",
    "Ki emlékszik még a Csepel Művek fénykorára? Írjatok egy emléket!",
    "Melyik a kedvenc sétaútvonalatok a Duna-parton?",
    "Hol lehet a legjobb lángost enni a környéken?",
    "Mi az, ami szerintetek a legjobban hiányzik a kerületből?",
    "Melyik játszóteret ajánlanátok kisgyerekes családoknak?",
    "Biciklivel, autóval, BKV-val vagy gyalog jártok inkább?",
    "Mi volt az első munkahelyetek a környéken?",
    "Melyik helyi pékséget ajánlanátok?",
    "Hol a legszebb a naplemente a környéken?",
    "Ki melyik iskolába járt a kerületben?",
    "Melyik környékbeli program volt idén a kedvencetek?",
    "Mi volt a legjobb koncert, amin a Barba Negrában voltatok?",
    "Hol tudtok jó fagyit enni a környéken?",
    "Ha egy dolgot megváltoztathatnátok a kerületben, mi lenne az?",
    "Melyik a kedvenc csepeli vagy erzsébeti utcátok, és miért?",
    "Kutyások! Hol a legjobb kutyafuttató a környéken?",
    "Melyik helyi sportegyesületnek szurkoltok?",
    "Mióta laktok a környéken?",
    "Melyik a kedvenc helyi éttermetek hétvégére?",
    "Ki jár futni a környéken? Merre a legjobb?",
    "Melyik régi üzletet vagy helyet sírjátok vissza leginkább?",
    "Szerintetek melyik a környék legszebb épülete?",
    "Strand, Duna-part vagy kert: hol töltitek a nyári hétvégéket?",
    "Melyik piacra jártok szívesen a környéken?",
    "Mit ajánlanátok annak, aki most költözött a kerületbe?",
    "Melyik a kedvenc ünnepi programotok a környéken?",
    "HÉV, busz vagy hajó: ti mivel jártok be a városba?",
    "Hol lehet a környéken a legjobban pihenni egy fárasztó nap után?",
    "Mi volt a legviccesebb dolog, ami veletek a környéken történt?",
    "Melyik helyi rendezvényre mennétek el idén mindenképp?",
    "Hol a legjobb hekk vagy halászlé a környéken?",
    "Ki jár horgászni a Ráckevei-Dunára?",
    "Melyik a kedvenc parkotok a környéken?",
    "Mit mutatnátok meg elsőként egy vendégnek, aki először jár nálunk?",
    "Kertes ház vagy lakótelep: ti hol laktok szívesebben?",
    "Melyik helyi szolgáltatót, mestert ajánlanátok jó szívvel?",
    "Milyen programot szeretnétek többet látni a kerületben?",
    "Hogy indul nálatok egy jó hétvége a környéken?",
]


def szoveg(nap):
    kerdes = KERDESEK[nap.toordinal() % len(KERDESEK)]
    st = Stilus("kerdes", nap.isoformat())
    sorok = [st.cim, st.vonal(), "", st.bevezeto, "", f"❓ {kerdes}", "",
             "👇 Írjátok meg kommentben, kíváncsian várom a válaszokat!"]
    if st.zaro:
        sorok += ["", st.zaro]
    sorok.append("#Csepel #Pesterzsébet #Szigetszentmiklós #kérdés")
    return "\n".join(sorok)
