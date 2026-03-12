from config import fd_api_get
from datetime import datetime

today = datetime.now().strftime("%Y-%m-%d")
print(f"A verificar jogos para: {today}\n")

r = fd_api_get("/matches", {"date": today})
matches = r.json().get("matches", [])
print(f"Total API: {len(matches)} jogos\n")

for m in matches:
    comp   = m["competition"]["name"]
    home   = m["homeTeam"]["name"]
    away   = m["awayTeam"]["name"]
    status = m["status"]
    print(f"  {comp} | {home} vs {away} | {status}")
