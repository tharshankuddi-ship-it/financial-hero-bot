"""
Run this ONCE locally to get your TikTok access token.
pip install requests
python get_tiktok_token.py
"""
import requests
import webbrowser
from urllib.parse import urlencode, parse_qs, urlparse

CLIENT_KEY    = "sbawgs3smrwhcdgcu8"
CLIENT_SECRET = "RanP8eBukOuvSVyQrgGJxQL9pTpzvFwv"
REDIRECT_URI  = "https://github.com/tharshankuddi-ship-it/financial-hero-bot"

# Step 1 — Open auth URL in browser
params = {
    "client_key":     CLIENT_KEY,
    "scope":          "user.info.basic,video.upload",
    "response_type":  "code",
    "redirect_uri":   REDIRECT_URI,
    "state":          "financial_hero",
}
auth_url = "https://www.tiktok.com/v2/auth/authorize/?" + urlencode(params)
print("\n🔗 Opening TikTok login in browser...")
print(f"\nIf browser doesn't open, go to:\n{auth_url}\n")
webbrowser.open(auth_url)

# Step 2 — Paste the redirect URL after login
print("After you log in, TikTok will redirect you to a URL.")
print("Copy the FULL URL from your browser and paste it here:")
redirect_url = input("\nPaste full redirect URL: ").strip()

# Step 3 — Extract code
parsed = urlparse(redirect_url)
code   = parse_qs(parsed.query).get("code", [None])[0]
if not code:
    print("❌ Could not find code in URL. Try again.")
    exit(1)

print(f"\n✅ Got auth code: {code[:20]}...")

# Step 4 — Exchange for access token
resp = requests.post(
    "https://open.tiktokapis.com/v2/oauth/token/",
    headers={"Content-Type": "application/x-www-form-urlencoded"},
    data={
        "client_key":    CLIENT_KEY,
        "client_secret": CLIENT_SECRET,
        "code":          code,
        "grant_type":    "authorization_code",
        "redirect_uri":  REDIRECT_URI,
    }
)
data = resp.json()
print(f"\nAPI Response: {data}")

if "access_token" in data:
    print(f"\n✅ SUCCESS!")
    print(f"\nAdd these to GitHub Secrets:")
    print(f"  TIKTOK_ACCESS_TOKEN  = {data['access_token']}")
    print(f"  TIKTOK_REFRESH_TOKEN = {data.get('refresh_token', 'N/A')}")
else:
    print(f"\n❌ Failed: {data}")
