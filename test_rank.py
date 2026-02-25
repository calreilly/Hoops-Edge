import requests
resp = requests.get("https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/rankings")
data = resp.json()
print(data["rankings"][0]["ranks"][0]["team"])
