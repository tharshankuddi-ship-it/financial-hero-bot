from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

CLIENT_CONFIG = {
    "installed": {
        "client_id": "764743703979-nif776k7898jfb9q6iqeojng9afbj76e.apps.googleusercontent.com",
        "client_secret": "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",
        "redirect_uris": ["http://localhost"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}

flow = InstalledAppFlow.from_client_config(CLIENT_CONFIG, SCOPES)
creds = flow.run_local_server(port=0)
print("Your Refresh Token:")
print(creds.refresh_token)