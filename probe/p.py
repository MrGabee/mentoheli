"""Make 2 fiók: webhook + Facebook-posztoló forgatókönyv létrehozása az API-n át.
A webhook címét csak titkosítva írja ki (a napló nyilvános)."""
import os, sys, json, subprocess, functools, requests
print = functools.partial(print, flush=True)
TOKEN = os.environ.get("MAKE2_API_TOKEN", "")
if not TOKEN:
    print("nincs MAKE2_API_TOKEN"); sys.exit(0)
H = {"Authorization": f"Token {TOKEN}", "Content-Type": "application/json"}
CSAK_NEZ = os.environ.get("CSAK_NEZ", "0") == "1"

def titkos(s):
    r = subprocess.run(["openssl", "pkeyutl", "-encrypt", "-pubin", "-inkey", "probe/pub.pem"],
                       input=s.encode(), capture_output=True)
    return subprocess.run(["base64", "-w0"], input=r.stdout, capture_output=True).stdout.decode()

base = None
for z in ["eu1", "eu2", "us1", "us2"]:
    r = requests.get(f"https://{z}.make.com/api/v2/users/me", headers=H, timeout=30)
    print(z, r.status_code)
    if r.status_code == 200:
        base = f"https://{z}.make.com/api/v2"; print("user:", r.json().get("authUser", {}).get("name")); break
if not base:
    sys.exit(0)
orgs = requests.get(f"{base}/organizations", headers=H, timeout=30).json().get("organizations", [])
for o in orgs:
    print("org", o["id"], o["name"], o.get("zone"), o.get("license", {}).get("operations"))
org = orgs[0]
base = f"https://{org['zone']}/api/v2"
teams = requests.get(f"{base}/teams", params={"organizationId": org["id"]}, headers=H, timeout=30).json().get("teams", [])
print("teams", [(t["id"], t["name"]) for t in teams])
team = teams[0]["id"]
conns = requests.get(f"{base}/connections", params={"teamId": team}, headers=H, timeout=30).json().get("connections", [])
print("conns", [(c["id"], c["name"], c["accountName"]) for c in conns])
hooks = requests.get(f"{base}/hooks", params={"teamId": team}, headers=H, timeout=30).json().get("hooks", [])
print("hooks", [(h["id"], h["name"], h.get("scenarioId")) for h in hooks])
scen = requests.get(f"{base}/scenarios", params={"teamId": team}, headers=H, timeout=30).json().get("scenarios", [])
print("scenarios", [(s["id"], s["name"], s.get("isActive")) for s in scen])
fb = [c for c in conns if c["accountName"] == "facebook"]
if CSAK_NEZ or not fb:
    print("csak nezelodes / nincs facebook kapcsolat"); sys.exit(0)

hook = next((h for h in hooks if h["name"] == "szines_posztok"), None)
if not hook:
    r = requests.post(f"{base}/hooks", headers=H, timeout=30, json={
        "name": "szines_posztok", "teamId": team, "typeName": "gateway-webhook",
        "method": False, "headers": False, "stringify": False})
    print("hook create", r.status_code, r.text[:300]); hook = r.json()["hook"]
bp = {"name": "Színes posztok – Facebook", "flow": [
    {"id": 1, "module": "gateway:CustomWebHook", "version": 1, "parameters": {"hook": hook["id"], "maxResults": 1}, "mapper": {},
     "metadata": {"designer": {"x": 0, "y": 0}, "interface": [{"name": "message", "type": "text"}, {"name": "link", "type": "text"}]}},
    {"id": 2, "module": "facebook-pages:CreatePost", "version": 6, "parameters": {"__IMTCONN__": fb[0]["id"]},
     "mapper": {"page_id": "104411308403346", "message": "{{1.message}}", "link": "{{1.link}}"},
     "metadata": {"designer": {"x": 300, "y": 0}}}],
    "metadata": {"instant": True, "version": 1, "scenario": {"roundtrips": 1, "maxErrors": 3, "autoCommit": True,
        "autoCommitTriggerLast": True, "sequential": False, "confidential": False, "dataloss": False, "dlq": False, "freshVariables": False}}}
meglevo = next((s for s in scen if s["name"] == bp["name"]), None)
if meglevo:
    sid = meglevo["id"]
    r = requests.patch(f"{base}/scenarios/{sid}", params={"confirmed": "true"}, headers=H, timeout=30,
                       json={"blueprint": json.dumps(bp)})
else:
    r = requests.post(f"{base}/scenarios", params={"confirmed": "true"}, headers=H, timeout=30, json={
        "teamId": team, "blueprint": json.dumps(bp), "scheduling": json.dumps({"type": "immediately"})})
print("scenario", r.status_code, r.text[:400])
sid = sid if meglevo else r.json()["scenario"]["id"]
r = requests.post(f"{base}/scenarios/{sid}/start", headers=H, timeout=30)
print("start", r.status_code, r.text[:300])
h = requests.get(f"{base}/hooks/{hook['id']}", headers=H, timeout=30).json()["hook"]
print("HOOK_URL_TITKOS", titkos(h["url"]))
