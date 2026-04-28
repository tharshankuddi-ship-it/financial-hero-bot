"""
refresh_tiktok_token.py
Runs in GitHub Actions BEFORE main.py to auto-refresh the TikTok token
and update the GitHub Secret automatically.
"""
import os
import sys
import requests
import json

CLIENT_KEY    = os.getenv("TIKTOK_CLIENT_KEY", "sbawgs3smrwhcdgcu8")
CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET", "RanP8eBukOuvSVyQrgGJxQL9pTpzvFwv")
REFRESH_TOKEN = os.getenv("TIKTOK_REFRESH_TOKEN")
GH_TOKEN      = os.getenv("GH_PAT")
GH_REPO       = os.getenv("GITHUB_REPOSITORY")  # auto set by Actions

def refresh_tiktok():
    if not REFRESH_TOKEN:
        print("No TIKTOK_REFRESH_TOKEN — skipping refresh")
        return

    resp = requests.post(
        "https://open.tiktokapis.com/v2/oauth/token/",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key":    CLIENT_KEY,
            "client_secret": CLIENT_SECRET,
            "grant_type":    "refresh_token",
            "refresh_token": REFRESH_TOKEN,
        },
        timeout=15,
    )
    data = resp.json()
    print(f"TikTok refresh response: {resp.status_code}")

    if "access_token" not in data:
        print(f"Refresh failed: {data}")
        sys.exit(1)

    new_access  = data["access_token"]
    new_refresh = data.get("refresh_token", REFRESH_TOKEN)
    print(f"New access token: {new_access[:20]}...")

    # Update GitHub Secrets via API
    if GH_TOKEN and GH_REPO:
        _update_github_secret("TIKTOK_ACCESS_TOKEN",  new_access,  GH_TOKEN, GH_REPO)
        _update_github_secret("TIKTOK_REFRESH_TOKEN", new_refresh, GH_TOKEN, GH_REPO)
    else:
        print("No GH_PAT set — writing tokens to env file instead")
        with open(os.environ.get("GITHUB_ENV", "/dev/stdout"), "a") as f:
            f.write(f"TIKTOK_ACCESS_TOKEN={new_access}\n")
            f.write(f"TIKTOK_REFRESH_TOKEN={new_refresh}\n")

    print("TikTok token refreshed successfully ✅")


def _update_github_secret(name, value, token, repo):
    """Update a GitHub Actions secret via the API."""
    # Get repo public key for encryption
    key_resp = requests.get(
        f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
        headers={"Authorization": f"token {token}",
                 "Accept": "application/vnd.github+json"},
        timeout=10,
    )
    key_data = key_resp.json()
    key_id   = key_data["key_id"]
    pub_key  = key_data["key"]

    # Encrypt the secret value
    encrypted = _encrypt_secret(pub_key, value)

    # Update the secret
    update_resp = requests.put(
        f"https://api.github.com/repos/{repo}/actions/secrets/{name}",
        headers={"Authorization": f"token {token}",
                 "Accept": "application/vnd.github+json"},
        json={"encrypted_value": encrypted, "key_id": key_id},
        timeout=10,
    )
    if update_resp.status_code in (201, 204):
        print(f"✅ GitHub Secret {name} updated")
    else:
        print(f"❌ Failed to update {name}: {update_resp.text}")


def _encrypt_secret(public_key_b64: str, secret_value: str) -> str:
    """Encrypt secret using repo's public key (libsodium)."""
    from base64 import b64decode, b64encode
    try:
        from nacl import encoding, public
        pub_key = public.PublicKey(
            b64decode(public_key_b64), encoding.RawEncoder
        )
        box       = public.SealedBox(pub_key)
        encrypted = box.encrypt(secret_value.encode("utf-8"))
        return b64encode(encrypted).decode("utf-8")
    except ImportError:
        print("PyNaCl not installed — install with: pip install PyNaCl")
        sys.exit(1)


if __name__ == "__main__":
    refresh_tiktok()
