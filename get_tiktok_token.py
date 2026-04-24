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
REDIRECT_URI  = "https://oauthresponse.com"

params = {
    "client_key":    CLIENT_KEY,
    "scope":         "user.info.basic,video.upload",
    "response_type": "code",
    "redirect_uri":  REDIRECT_URI,
    "state":         "financial_hero",
}
auth_url = "https://www.tiktok.com/v2/auth/authorize/?" + urlencode(params)
print("\nOpening TikTok login in browser...")
print(f"\nIf browser does not open, go to:\n{auth_url}\n")
webbrowser.open(auth_url)

print("\nAfter logging in, you will land on oauthresponse.com")
print("It will show your CODE on the page clearly.")
print("Copy the FULL URL from your browser address bar and paste below:")
redirect_url = input("\nPaste full redirect URL: ").strip()

parsed = urlparse(redirect_url)
code   = parse_qs(parsed.query).get("code", [None])[0]
if not code:
    print("Could not find code. Copy the full URL from the address bar.")
    exit(1)

print(f"\nGot code: {code[:20]}...")

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
print(f"\nResponse: {data}")

if "access_token" in data:
    print(f"\nSUCCESS! Add to GitHub Secrets:")
    print(f"  TIKTOK_ACCESS_TOKEN  = {data['access_token']}")
    print(f"  TIKTOK_REFRESH_TOKEN = {data.get('refresh_token', 'N/A')}")
else:
    print(f"\nFailed: {data}")
