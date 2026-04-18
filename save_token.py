from google_auth_oauthlib.flow import InstalledAppFlow
import glob, json

client_secret = glob.glob('E:/client_secret*.json')[0]
flow = InstalledAppFlow.from_client_secrets_file(
    client_secret,
    ['https://www.googleapis.com/auth/youtube.upload']
)
creds = flow.run_local_server(port=0, access_type='offline', prompt='consent')
with open('E:/files/token.json', 'w') as f:
    f.write(creds.to_json())
print('Done! token.json saved.')
