"""Quick diagnostic: why is John Bouchard denied access to RFPO 56?"""
import requests, json

API = "https://rfpo-api.uscar.org"

# Login as admin
r = requests.post(f"{API}/api/auth/login", json={"username": "admin@rfpo.com", "password": "admin123"})
admin_token = r.json()["token"]
headers = {"Authorization": f"Bearer {admin_token}"}

# Get RFPO 56
rfpo = requests.get(f"{API}/api/rfpos/56", headers=headers).json()["rfpo"]
print("=== RFPO 56 ===")
print(f"  rfpo_id:       {rfpo['rfpo_id']}")
print(f"  requestor_id:  {rfpo['requestor_id']}")
print(f"  team_id:       {rfpo['team_id']}")
print(f"  project_id:    {rfpo['project_id']}")
print(f"  consortium_id: {rfpo['consortium_id']}")
print(f"  status:        {rfpo['status']}")

# Get all users, find John Bouchard
users = requests.get(f"{API}/api/users", headers=headers).json()["users"]
john = [u for u in users if u.get("last_name") == "Bouchard" and u.get("first_name") == "John"]
if john:
    jb = john[0]
    print("\n=== John Bouchard ===")
    print(f"  record_id:    {jb['record_id']}")
    print(f"  email:        {jb.get('email')}")
    print(f"  permissions:  {jb.get('permissions')}")
    print(f"  is_approver:  {jb.get('is_approver')}")
    print(f"  is_super_admin: {jb.get('is_super_admin', 'N/A')}")
    
    # Get John's teams
    teams = requests.get(f"{API}/api/teams", headers=headers).json()
    team_list = teams.get("teams", [])
    print(f"\n=== Teams (total: {len(team_list)}) ===")
    for t in team_list:
        print(f"  Team id={t['id']} name={t.get('name','')} viewer_user_ids={t.get('viewer_user_ids',[])} admin_user_ids={t.get('admin_user_ids',[])}")
    
    # Check team 6 specifically
    rfpo_team_id = rfpo['team_id']
    matching_team = [t for t in team_list if t['id'] == rfpo_team_id]
    if matching_team:
        mt = matching_team[0]
        print(f"\n=== RFPO's Team (id={rfpo_team_id}) ===")
        print(f"  name: {mt.get('name')}")
        print(f"  viewer_user_ids: {mt.get('viewer_user_ids')}")
        print(f"  admin_user_ids: {mt.get('admin_user_ids')}")
    
    # Login as John to see what teams he has
    print(f"\n=== Login as John ({jb['email']}) ===")
    jr = requests.post(f"{API}/api/auth/login", json={"username": jb["email"], "password": "admin123"})
    if jr.status_code == 200:
        jtoken = jr.json()["token"]
        jheaders = {"Authorization": f"Bearer {jtoken}"}
        
        # Try accessing RFPO 56 directly
        r56 = requests.get(f"{API}/api/rfpos/56", headers=jheaders)
        print(f"  GET /api/rfpos/56 => {r56.status_code}: {r56.json().get('message', 'OK')}")
        
        # Check John's profile
        me = requests.get(f"{API}/api/auth/me", headers=jheaders)
        if me.status_code == 200:
            me_data = me.json().get("user", me.json())
            print(f"  /auth/me record_id: {me_data.get('record_id')}")
            print(f"  /auth/me permissions: {me_data.get('permissions')}")
            print(f"  /auth/me teams: {me_data.get('teams', 'N/A')}")
    else:
        print(f"  Login failed: {jr.status_code} {jr.text}")
else:
    print("John Bouchard NOT FOUND in users")

# Also check project access
print(f"\n=== Project {rfpo['project_id']} ===")
projects = requests.get(f"{API}/api/projects", headers=headers).json()
proj_list = projects.get("projects", [])
for p in proj_list:
    if str(p.get("project_id")) == str(rfpo["project_id"]) or str(p.get("id")) == str(rfpo["project_id"]):
        print(f"  Project: {p.get('name')} ref={p.get('ref')}")
        print(f"  rfpo_viewer_user_ids: {p.get('rfpo_viewer_user_ids', 'N/A')}")
        print(f"  rfpo_admin_user_ids: {p.get('rfpo_admin_user_ids', 'N/A')}")
        break
