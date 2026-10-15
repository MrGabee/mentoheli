import requests, json, time
B="http://futar.bkk.hu/bkk-utvonaltervezo-api/ws/otp/api/where"
K="key=apaiary-test&version=3&appVersion=apiary-1.0"
H={"User-Agent":"Mozilla/5.0"}
for rid in ["BKK_1480","BKK_1510","BKK_0350","BKK_0360"]:
    r=requests.get(f"{B}/vehicles-for-route.json?{K}&routeId={rid}&related=false",headers=H,timeout=20)
    print("=====",rid,r.status_code)
    try:
        d=r.json()["data"]; L=d.get("list") or []
        print("n vehicles",len(L))
        if L: print(json.dumps(L[0],ensure_ascii=False)[:900])
        tid=next((v.get("tripId") for v in L if v.get("tripId")),None)
        if tid and rid=="BKK_1480":
            t=requests.get(f"{B}/trip-details.json?{K}&tripId={tid}&includeReferences=stops",headers=H,timeout=20).json()["data"]
            e=t["entry"]; st=e.get("stopTimes",[])
            print("trip keys",list(e.keys()))
            stops=t.get("references",{}).get("stops",{})
            for s in st[:40]:
                print(stops.get(s.get("stopId"),{}).get("name"), s.get("arrivalTime"), s.get("predictedArrivalTime"), s.get("departureTime"), s.get("predictedDepartureTime"))
    except Exception as x: print("ERR",x,r.text[:300])
