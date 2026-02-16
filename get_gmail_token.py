"""
Run this script locally to get your Gmail OAuth refresh token
"""
from google_auth_oauthlib.flow import InstalledAppFlow
import json

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

print("Gmail OAuth Token Generator")
print("=" * 50)
print("\n1. Download your OAuth client credentials JSON from Google Cloud Console")
print("2. Save it as 'credentials.json' in this directory")
print("3. Press Enter to continue...")
input()

try:
    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
    creds = flow.run_local_server(port=0)
    
    print("\n" + "=" * 50)
    print("✅ SUCCESS! Add these to Railway:")
    print("=" * 50)
    
    # Parse credentials JSON to get client_id and client_secret
    with open('credentials.json', 'r') as f:
        cred_data = json.load(f)
        client_id = cred_data['installed']['client_id']
        client_secret = cred_data['installed']['client_secret']
    
    print(f"\nGMAIL_CLIENT_ID={client_id}")
    print(f"GMAIL_CLIENT_SECRET={client_secret}")
    print(f"GMAIL_REFRESH_TOKEN={creds.refresh_token}")
    print(f"GMAIL_USER_EMAIL=roaam5182@gmail.com")
    print("\n" + "=" * 50)
    
except FileNotFoundError:
    print("\n❌ Error: credentials.json not found!")
    print("Download it from Google Cloud Console and save it here.")
except Exception as e:
    print(f"\n❌ Error: {e}")
