import requests
API = "https://rfpo-api.uscar.org"
r = requests.post(f"{API}/api/auth/login", json={"username": "admin@rfpo.com", "password": "admin123"})
headers = {"Authorization": f"Bearer {r.json()['token']}"}
users = requests.get(f"{API}/api/users", headers=headers).json()["users"]
for u in users:
    print(f"  {u['record_id']:12s} {u.get('first_name',''):12s} {u.get('last_name',''):15s} {u.get('email','')}")
