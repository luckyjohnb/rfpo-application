import requests, json
API = "https://rfpo-api.uscar.org"
r = requests.post(f"{API}/api/auth/login", json={"username": "admin@rfpo.com", "password": "admin123"})
admin_headers = {"Authorization": f"Bearer {r.json()['token']}"}

# RFPO 56 details
rfpo = requests.get(f"{API}/api/rfpos/56", headers=admin_headers).json()["rfpo"]
print(f"RFPO 56: team_id={rfpo['team_id']}, project_id={rfpo['project_id']}, requestor_id={rfpo['requestor_id']}")

# Get John's user details directly
john = requests.get(f"{API}/api/users/00000002", headers=admin_headers)
if john.status_code == 200:
    jd = john.json().get("user", john.json())
    print(f"\nJohn: record_id={jd.get('record_id')}, permissions={jd.get('permissions')}, is_approver={jd.get('is_approver')}")
    print(f"  teams: {jd.get('teams', 'N/A')}")

# Get teams and check team 6
teams = requests.get(f"{API}/api/teams", headers=admin_headers).json()
team_list = teams.get("teams", [])
for t in team_list:
    # Check if John is in this team
    viewers = t.get("viewer_user_ids", []) or []
    admins = t.get("admin_user_ids", []) or []
    members = t.get("member_ids", []) or []
    if "00000002" in str(viewers) + str(admins) + str(members) or t["id"] == rfpo["team_id"]:
        print(f"\nTeam id={t['id']} name={t.get('name','')}")
        print(f"  viewer_user_ids: {viewers}")
        print(f"  admin_user_ids: {admins}")
        if t.get("member_ids"):
            print(f"  member_ids: {members}")

# Login as John
print("\n=== Login as John ===")
jr = requests.post(f"{API}/api/auth/login", json={"username": "johnbouchard@icloud.com", "password": "admin123"})
if jr.status_code == 200:
    jtoken = jr.json()["token"]
    jheaders = {"Authorization": f"Bearer {jtoken}"}
    
    # Check /auth/me 
    me = requests.get(f"{API}/api/auth/me", headers=jheaders)
    if me.status_code == 200:
        me_data = me.json().get("user", me.json())
        print(f"  record_id: {me_data.get('record_id')}")
        print(f"  permissions: {me_data.get('permissions')}")
        print(f"  teams count: {len(me_data.get('teams', []))}")
        for t in me_data.get("teams", []):
            print(f"    team id={t.get('id')} name={t.get('name','')}")
    
    # Try accessing RFPO 56
    r56 = requests.get(f"{API}/api/rfpos/56", headers=jheaders)
    print(f"\n  GET /api/rfpos/56 => {r56.status_code}")
    if r56.status_code != 200:
        print(f"  Response: {r56.json()}")
    
    # Check RFPO list
    rlist = requests.get(f"{API}/api/rfpos", headers=jheaders)
    print(f"  GET /api/rfpos => {rlist.status_code}, total={rlist.json().get('total',0)}")
else:
    print(f"  Login FAILED: {jr.status_code} - {jr.text}")

# Check project 00000014 for viewer access
print(f"\n=== Project 00000014 ===")
proj = requests.get(f"{API}/api/projects/00000014", headers=admin_headers)
if proj.status_code == 200:
    pd = proj.json().get("project", proj.json())
    print(json.dumps(pd, indent=2, default=str))
else:
    # Try listing all projects
    projs = requests.get(f"{API}/api/projects", headers=admin_headers).json()
    for p in projs.get("projects", []):
        pid = p.get("project_id", p.get("id"))
        if str(pid) == "00000014":
            print(f"  name={p.get('name')} ref={p.get('ref')}")
            print(f"  rfpo_viewer_user_ids: {p.get('rfpo_viewer_user_ids')}")
            break
